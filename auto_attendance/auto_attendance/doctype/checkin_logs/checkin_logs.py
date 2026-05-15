# Copyright (c) 2026, GreyCube Technologies and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _
from frappe.utils import get_datetime, get_link_to_form, now_datetime
from frappe.model.document import Document
from hrms.hr.doctype.employee_checkin.employee_checkin import add_log_based_on_employee_field


class CheckinLogs(Document):
	def after_insert(self):
		print(self.name,"-----------")
		frappe.enqueue(create_employee_checkins, docname=self.name, queue="long",job_name="Create Employee Checkins for date {0}".format(self.checkin_date))
		# create_employee_checkins(self.name)

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

			for record in checkin_data.get("attendance-daily"):
				user_id = record.get("userid")
				
				# Determine the Employee ID linked to this userid
				# Assuming 'attendance_device_id' or a custom field stores the Matrix UserID
				employee = frappe.db.get_value("Employee", {"attendance_device_id": user_id}, "name")
				
				if not employee:
					add_error_to_doc(checkin_log_doc, f"Employee not found for User ID: {user_id}", "Employee Not Found")
					# frappe.log_error(f"Employee not found for User ID: {user_id}", "Attendance Sync Error")
					continue

				# Iterate through possible punch keys from punch1 to punch12
				for i in range(1, 13):
					punch_key = f"punch{i}"
					punch_time_str = record.get(punch_key)

					# Only proceed if the punch key exists and has a value
					if punch_time_str:
						try:
							# Convert string to Frappe-friendly datetime
							# Your format: "12/05/2026 08:31:39"
							punch_time = get_datetime(punch_time_str)

							# Avoid creating duplicate check-ins for the same employee and time
							if not frappe.db.exists("Employee Checkin", {
								"employee": employee,
								"time": punch_time
							}):
								# Create the Checkin Document
								# doc = frappe.get_doc({
								# 	"doctype": "Employee Checkin",
								# 	"employee": employee,
								# 	"time": punch_time,
								# 	"device_id": "Matrix_Server", # Optional: track source
								# 	"custom_working_minutes":record.get("worktime")
								# 	# "log_type": "IN" if i % 2 != 0 else "OUT" # Logical guess: odd=IN, even=OUT
								# })
								# doc.insert()
								emp_checkin_doc = add_log_based_on_employee_field(
									user_id,
									punch_time,
									device_id=None,
									log_type=None,
									skip_auto_attendance=0,
									employee_fieldname="attendance_device_id",
									latitude=None,
									longitude=None,
								)
								frappe.db.set_value("Employee Checkin", emp_checkin_doc.name,"custom_checkin_log_reference",checkin_log_doc.name)
								frappe.db.set_value("Employee Checkin", emp_checkin_doc.name,"custom_working_minutes",record.get("worktime"))
								checkin_count += 1
								
						except Exception as e:
							add_error_to_doc(checkin_log_doc, f"Error processing {punch_key} for User ID {user_id}: {str(e)}", "Error in checkin data")
							# frappe.log_error(f"Error processing {punch_key} for {user_id}: {str(e)}")

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