// Copyright (c) 2025, GreyCube Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Auto Attendance Settings", {
	create_checkin(frm) {
        if (frm.doc.attendance_run_date == undefined || frm.doc.attendance_run_date == "") {
            frappe.throw("Please select date first");
        }
        frappe.call({
            method: "auto_attendance.api.create_checkin_for_selected_date",
            args: {
                date : frm.doc.attendance_run_date
            },
            callback: function (r) {
                
            }
        })
	},
});
