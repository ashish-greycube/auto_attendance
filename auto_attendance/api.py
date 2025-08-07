import frappe
import requests
from frappe import _
from frappe.utils import getdate, now_datetime
from hrms.hr.doctype.employee_checkin.employee_checkin import add_log_based_on_employee_field

@frappe.whitelist()
def get_data_and_create_checkin():
	print("==========================")
	auto_atten_settings = frappe.get_doc("Auto Attendance Settings","Auto Attendance Settings")
	print(getdate(auto_atten_settings.from_date), getdate(auto_atten_settings.to_date))
	get_data_from_api(auto_atten_settings.last_sync_of_checkin_data,now_datetime())

	from_date = getdate(auto_atten_settings.from_date)
	to_date = getdate(auto_atten_settings.to_date)

@frappe.whitelist()				
def get_data_from_api(from_date,to_date):
	response = requests.get(f"https://sohcm.com/SmartApp_ess/api/SwipeDetails/GetDeviceLogs?APIKey=233916012427&AccountName=ACE&FromDate={getdate(from_date)}&ToDate={getdate(to_date)}")
	print(len(response.json()),"---------------",now_datetime())
	device_data = response.json()
	count = 0
	if len(device_data)>0:
		for record in device_data:
			print(count := count + 1,"--------")
			if record.get("UserId")=="108":
				print(" for 100 id")
				create_employee_checkin_based_on_device_data(record.get("UserId"),record.get("LogDate"),record.get("DeviceSName"))
				count += 1
			frappe.publish_progress(count / len(device_data) * 100, title=_("Creating Employee Checkins..."))
	frappe.db.set_value("Auto Attendance Settings","Auto Attendance Settings","last_sync_of_checkin_data",to_date)

def create_employee_checkin_based_on_device_data(user_id,timestamp,device_id):
	try:
		add_log_based_on_employee_field(
			user_id,
			timestamp,
			device_id=device_id,
			log_type=None,
			skip_auto_attendance=0,
			employee_fieldname="name",
			latitude=None,
			longitude=None)
	except Exception as e:
		frappe.log_error(_("Employee Checkin Creation Error"),str(e))	
