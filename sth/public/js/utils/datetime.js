// Copyright (c) 2025, DAS and Contributors
// MIT License. See license.txt

frappe.provide("sth.datetime");

sth.datetime = {
    month_start: function (d) {
		return moment(d).startOf("month").format();
	},

	month_end: function (d) {
		return moment(d).endOf("month").format();
	}
}