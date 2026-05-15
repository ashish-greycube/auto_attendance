import frappe
import json
import requests
from frappe import _
from frappe.utils import getdate, now_datetime, add_to_date, get_link_to_form
from hrms.hr.doctype.employee_checkin.employee_checkin import add_log_based_on_employee_field
from requests.exceptions import (
	ConnectionError, 
	Timeout, 
	HTTPError, 
	RequestException
)

@frappe.whitelist()
def create_checkin_for_selected_date(date):
	if not date:
		frappe.throw(_("Please provide a date."))

	try:
		checkin_log = get_data_from_api_and_create_checkin(date)
		frappe.msgprint(_("Check-in data fetched and processed successfully for {0}.").format(date))
		settings_doc = frappe.get_doc("Auto Attendance Settings", "Auto Attendance Settings")
		settings_doc.add_comment("Comment","Checkin Log reference : {0}".format(get_link_to_form("Checkin Logs",checkin_log)))
	except Exception as e:
		frappe.log_error(message="Error in create_checkin_for_selected_date: {0}".format(str(e)), title="Check-in Creation Failed")
		frappe.msgprint(_("An error occurred while fetching or processing check-in data for {0}. Please check the error logs.").format(date), alert=True)

@frappe.whitelist()				
def get_data_from_api_and_create_checkin(attendance_run_date=None):
	checkin_request_date = getdate(attendance_run_date) if attendance_run_date else add_to_date(getdate(), days=-1)

	settings_doc = frappe.get_cached_doc("Auto Attendance Settings","Auto Attendance Settings")
	### remove / from url if exists
	url = settings_doc.url
	user_id = settings_doc.userid
	password = settings_doc.get_password("password")
	if url.endswith("/"):
		url = url[:-1]
	
	if url and user_id and password:
		date_range = f"{checkin_request_date.strftime('%d%m%Y')}-{checkin_request_date.strftime('%d%m%Y')}"

		checkin_log = frappe.new_doc("Checkin Logs")
		checkin_log.checkin_date = checkin_request_date

		try:
			# Make the GET request with Basic Auth
			response = requests.get(f"{url}?action=get;date-range={date_range};format=json", auth=(user_id, password))
			
			# Check if the request was successful (status code 200)
			response.raise_for_status()
			
			# Parse the response as JSON
			json_data = response.json()

			total_punches = get_total_punches(json_data)
			print("Total Punches: ", total_punches)
			checkin_log.checkin_data = json.dumps(json_data, indent=4)
			checkin_log.total_punch_count = total_punches
			checkin_log.insert(ignore_permissions=True)

			settings_doc = frappe.get_doc("Auto Attendance Settings", "Auto Attendance Settings")
			settings_doc.last_sync_of_checkin_data = checkin_request_date
			settings_doc.save(ignore_permissions=True)
			return checkin_log.name

		except Timeout:
			error_log = frappe.log_error(message="Error: The request timed out after 30 seconds.", title="Attendance API Fetch Failed")
		except ConnectionError:
			error_log = frappe.log_error(message="Error: Failed to connect to the Matrix server. Check DNS or Firewall.", title="Attendance API Fetch Failed")
		except HTTPError as e:
			status_code = e.response.status_code
			if status_code == 401:
				msg = "Error: Unauthorized. Check API credentials."
			elif status_code == 404:
				msg = "Error: API endpoint not found (404)."
			else:
				msg = f"Error: Server returned HTTP status {status_code}."
			error_log = frappe.log_error(message=msg, title="Attendance API Fetch Failed")
		except RequestException as e:
			error_log = frappe.log_error(message=frappe.get_traceback(), title="General API Error : {0}".format(str(e)))
		except Exception as e:
			error_log = frappe.log_error(message=frappe.get_traceback() ,title="System Error")
			frappe.throw(_("An error occurred while fetching check-in data. Please check the error logs. : {0}".format(get_link_to_form("Error Log",error_log.name))))
	else:
		frappe.throw(_("Please set the API URL, User ID, and Password in Auto Attendance Settings."))
def get_total_punches(json_data):
    total_punches = 0

    # Extract the list of records safely
    records = json_data.get("attendance-daily", [])

    for record in records:
        # Check for each punch key (punch1 to punch12)
        for i in range(1, 13):
            punch_key = f"punch{i}"

            # If the punch key exists and is not empty, increment the total counter
            if record.get(punch_key, "").strip() != "":
                total_punches += 1

    return total_punches
