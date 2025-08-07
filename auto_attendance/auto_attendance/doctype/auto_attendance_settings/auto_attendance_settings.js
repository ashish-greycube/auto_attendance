// Copyright (c) 2025, GreyCube Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Auto Attendance Settings", {
	create_checkin(frm) {
        frappe.call({
            method: "auto_attendance.api.get_data_from_api",
            args: {
                from_date : frm.doc.from_date,
	            to_date : frm.doc.to_date
            },
            callback: function (r) {
                
            }
        })
	},
});
