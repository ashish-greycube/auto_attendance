# Copyright (c) 2026, GreyCube Technologies and contributors
# For license information, please see license.txt

import frappe
import json
from datetime import datetime
from frappe import _
from frappe.utils import get_datetime, get_link_to_form, now_datetime
from frappe.model.document import Document
from hrms.hr.doctype.employee_checkin.employee_checkin import add_log_based_on_employee_field


class CheckinLogs(Document):
	def after_insert(self):
		print(self.name,"-----------")
		frappe.enqueue(create_employee_checkins, docname=self.name, queue="long",job_name="Create Employee Checkins for date {0}".format(self.checkin_date))
		# create_employee_checkins(self.name)


# The device reports direction on every event; 0 is a reader entry, 1 an exit.
LOG_TYPE_BY_ENTRY_EXIT = {"0": "IN", "1": "OUT"}

# The panel sends day-first timestamps: "12/07/2026 08:31:39" is 12 July.
DEVICE_DATETIME_FORMATS = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")


def parse_device_datetime(value):
	"""Read the device's day-first timestamp.

	`frappe.utils.get_datetime` falls through to dateutil, which reads an
	ambiguous `dd/mm/yyyy` as *month*-first. Every punch on days 1-12 therefore
	landed in the wrong month - 12/07/2026 became 7 December, 01/08/2026 became
	8 January - while days 13-31 parsed correctly because no month can be 13.
	The corruption is invisible in totals: the swap is symmetric, so 7 August
	lands on 8 July and vice versa, and both days still look populated.

	Parse the format explicitly instead of guessing at it.
	"""
	value = (value or "").strip()
	for fmt in DEVICE_DATETIME_FORMATS:
		try:
			return datetime.strptime(value, fmt)
		except ValueError:
			continue
	raise ValueError(f"Unrecognised device timestamp: {value!r}")


def iter_punches(checkin_data):
	"""Yield (user_id, punch_time, log_type) from either device payload shape.

	Current payload is `event-ta-date` - one record per punch, carrying the
	IN/OUT direction. Checkin Logs stored before the switch hold the older
	`attendance-daily` shape (one record per employee-day, punch1..punch12,
	no direction), so keep reading those as well: reprocessing an old log
	should still work.
	"""
	events = checkin_data.get("event-ta-date")
	if events is not None:
		for record in events:
			yield (
				record.get("userid"),
				record.get("eventdatetime"),
				LOG_TYPE_BY_ENTRY_EXIT.get(str(record.get("entryexittype"))),
			)
		return

	for record in checkin_data.get("attendance-daily") or []:
		for i in range(1, 13):
			punch_time_str = record.get(f"punch{i}")
			if punch_time_str:
				yield record.get("userid"), punch_time_str, None

@frappe.whitelist()
def create_employee_checkins(docname):
	print(docname,"==============")
	checkin_log_doc = frappe.get_doc("Checkin Logs", docname)
	checkin_log_doc.log_status = "In Progress"
	checkin_log_doc.job_start_time = now_datetime()
	checkin_data = []
	try:
		try:
			checkin_data = frappe.parse_json(checkin_log_doc.checkin_data)
		except Exception as e:
			add_error_to_doc(checkin_log_doc, message=None, title="JSON Parse Error")
			checkin_log_doc.log_status = "Error"  # Absolute failure to parse input data
			checkin_log_doc.job_end_time = now_datetime()
			checkin_log_doc.save(ignore_permissions=True)
			frappe.db.commit()

		# checkin_data = frappe.parse_json(data)
		
		checkin_count = 0
		checkin_log_doc.error = ""

		if checkin_data:
			# print("Creating Employee Checkins from API data...",checkin_data)

			# One lookup for the whole run - the event feed is per punch, so a
			# query per record would be several hundred round trips a day.
			employee_by_device_id = {
				row.attendance_device_id: row.name
				for row in frappe.get_all(
					"Employee",
					filters={"attendance_device_id": ["!=", ""]},
					fields=["name", "attendance_device_id"],
				)
				if row.attendance_device_id
			}
			# A device id nobody is mapped to would otherwise raise one error per
			# punch; report each unknown id once instead.
			unknown_device_ids = set()

			for user_id, punch_time_str, log_type in iter_punches(checkin_data):
				if not user_id or not punch_time_str:
					continue

				employee = employee_by_device_id.get(str(user_id))
				if not employee:
					if user_id not in unknown_device_ids:
						unknown_device_ids.add(user_id)
						add_error_to_doc(checkin_log_doc, f"Employee not found for User ID: {user_id}", "Employee Not Found")
					continue

				try:
					# Device format: "12/05/2026 08:31:39" - day first
					punch_time = parse_device_datetime(punch_time_str)

					# Avoid creating duplicate check-ins for the same employee and time
					if frappe.db.exists("Employee Checkin", {
						"employee": employee,
						"time": punch_time
					}):
						continue

					emp_checkin_doc = add_log_based_on_employee_field(
						user_id,
						punch_time,
						device_id=None,
						log_type=log_type,
						skip_auto_attendance=0,
						employee_fieldname="attendance_device_id",
						latitude=None,
						longitude=None,
					)
					frappe.db.set_value("Employee Checkin", emp_checkin_doc.name,"custom_checkin_log_reference",checkin_log_doc.name)
					checkin_count += 1

				except Exception as e:
					add_error_to_doc(checkin_log_doc, f"Error processing punch at {punch_time_str} for User ID {user_id}: {str(e)}", "Error in checkin data")

			# Commit changes to database
			frappe.db.commit()
			if checkin_log_doc.error:
				checkin_log_doc.log_status = "Finished With Error"
			else:
				checkin_log_doc.log_status = "Finished"

			checkin_log_doc.employee_checkin_count = checkin_count
			checkin_log_doc.job_end_time = now_datetime()
			checkin_log_doc.save()
	except Exception as e:
		add_error_to_doc(checkin_log_doc)
		checkin_log_doc.log_status = "Error"
		checkin_log_doc.job_end_time = now_datetime()
		checkin_log_doc.save(ignore_permissions=True)

def add_error_to_doc(doc, message=None, title=None):
	"""
	Simple helper to append messages to the error field 
	on a new line without using 'self'
	"""
	title = title if title else "Check-in Log Processing Failed"
	message = message if message else frappe.get_traceback()
	error_log = error_log=frappe.log_error(
				title= title,
				message=message,
		)
	error_url = get_link_to_form("Error Log", error_log.name)
	
	hyperlink = f'<a href="{error_url}" target="_blank">View Error Log ({error_log.name})</a>'
	
	# 3. Append the hyperlink on a new line
	new_line = f"\n{title} : "+f"{error_url}" if doc.error else f"{title} : "+f"{error_url}"
	doc.error = (doc.error or "") + new_line
	doc.save()