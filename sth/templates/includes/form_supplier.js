//const today = new Date().toISOString().split("T")[0]

class FormSupplier {
    constructor() {
        this.initData()
        this.initEvent()
        this.initAction()
    }

    initData() {
        this.wrapperItems = $("#items tbody")
        this.opt = {
            digitGroupSeparator: ',',
            decimalCharacter: '.',
            decimalPlaces: 2,
            emptyInputBehavior: 'zero'
        }
        this.charges = {
            discount: 0,
            ongkos_angkut: 0,
            ppn_ongkos_angkut: 0,
            pbbkb: 0,
            pph_22: 0,
        }
        this.wrapperDiscount = $('tr[data-type="discount"]')
    }

    initEvent() {
        $(".datepicker").datepicker({
            dateFormat: "yy-mm-dd",
        }).datepicker("setDate", new Date());

        this.initSelect2("select[name='country[]']");
        AutoNumeric.multiple('.number-format', this.opt);
        AutoNumeric.getAutoNumericElement('input[name="ppn_ongkos_angkut"]').set(11);
    }

    initSelect2(el) {
        $(el).select2({
            dropdownParent: $('body'),
            width: '100%'
        })
        $("select[name='country[]']").val("Indonesia").trigger("change")
    }

    initMoney(el) {
        return new AutoNumeric(el, this.opt);
    }

    toggleDeleteBtn() {
        let checkedRow = $(".form-check-input-row:checked")
        if (checkedRow.length) {
            $("#btn-delete").show()
        } else {
            $("#btn-delete").hide()
        }
    }

    calculateNetTotals() {
        let net_total = 0
        this.wrapperItems.find('tr').each((idx, el) => {
            net_total += parseFloat($(el).find('td[data-field="subtotal"] .display').attr('data-value'))
        })
        this.net_total = net_total
        $('input[name="net_total"]').val(`Rp.${this.numberFormat(net_total)}`)

        this.calculateDiscount()
        this.calculateGrandTotals()
    }

    calculateGrandTotals() {
        // console.log(net_total, discount, ongkos_angkut, ppn_ongkos_angkut, pbbkb, pph_22)

        const ppn_ongkos_amount = parseFloat($("tr[data-type='ppn_ongkos_angkut']").find('.amount').attr('data-value'))
        const discount_amount = parseFloat(this.wrapperDiscount.find('.amount').attr('data-value'))

        const grand_total = this.net_total - discount_amount + this.charges.ongkos_angkut + ppn_ongkos_amount + this.charges.pbbkb + this.charges.pph_22
        $('input[name="grand_total"]').val(`Rp.${this.numberFormat(grand_total)}`)
    }

    numberFormat(el) {
        return numeral(el).format('0,0')
    }

    calculateAmount(type, row) {
        // row harus element
        if (type == "items") {
            let rate = numeral(row.find("input[name='rate[]']").val())
            let qty = row.find("input[name='qty[]']").val()
            let amount = rate.value() * qty

            let elSubtotal = row.find("td[data-field='subtotal'] .display")
            elSubtotal.text(`Rp.${this.numberFormat(amount)}`)
            elSubtotal.attr('data-value', amount)
        } else if (type == "charges") {
            if (row.attr('data-type') == "discount") {
                this.calculateDiscount()
            } else if (row.attr('data-type') == "ppn_ongkos_angkut") {
                this.calculatePpnOngkos()
            } else {
                const amount = numeral(row.find('input').val()).value()
                this.charges[row.attr('data-type')] = amount
                row.find('.amount').text(`Rp. ${this.numberFormat(amount)}`)

                if (row.attr('data-type') == "ongkos_angkut") {
                    this.calculatePpnOngkos()
                }
            }
        }
    }

    calculateDiscount() {
        const percent = numeral(this.wrapperDiscount.find('input').val()).value()
        const amount = this.net_total * percent / 100
        this.charges.discount = percent
        this.wrapperDiscount.find('.amount').text(`Rp. ${this.numberFormat(amount)}`).attr("data-value", amount)
    }

    calculatePpnOngkos() {
        let ppn_ongkos = $("#charges tr[data-type='ppn_ongkos_angkut']")
        const ppn_ongkos_val = numeral(ppn_ongkos.find('input').val()).value()
        let amount_ppn = this.charges.ongkos_angkut * ppn_ongkos_val / 100
        this.charges.ppn_ongkos_angkut = ppn_ongkos_val
        ppn_ongkos.find('.amount').text(`Rp. ${this.numberFormat(amount_ppn)}`).attr("data-value", amount_ppn)
    }

    refreshIdx() {
        $("td[data-field='idx']").each((idx, el) => {
            $(el).text(idx + 1)
        })
    }

    uploadFile(file, doctype, docname) {
        let form_data = new FormData();
        form_data.append('file', file);
        form_data.append('doctype', doctype);
        form_data.append('docname', docname);
        form_data.append('fieldname', "custom_file_upload");
        form_data.append('is_private', "1");

        $.ajax({
            url: '/api/method/upload_file',
            method: 'POST',
            data: form_data,
            processData: false,
            contentType: false,
            headers: {
                "Accept": "application/json",
                "X-Frappe-CSRF-Token": "{{ csrf_token }}"
            },
            success: function (res) {
                window.location.replace("/success-page")
            },
            error: function (err) {
                console.error("Error:", err);
            }
        })
    }

    initAction() {
        var self = this

        this.wrapperItems.on("input", "input[name='rate[]'],input[name='qty[]']", function () {
            let row = $(this).closest("tr")
            self.calculateAmount("items", row)
            self.calculateNetTotals()
            self.calculateGrandTotals()
        })

        $("#charges tbody input").on('input', function () {
            let row = $(this).closest("tr")
            self.calculateAmount("charges", row)
            self.calculateGrandTotals()
        })

        $(".form-check-input-row").on("change", function () {
            self.toggleDeleteBtn()
        })

        $("#checkAll").on("click", function (e) {
            $(".form-check-input-row").prop("checked", this.checked)
            self.toggleDeleteBtn()
        })


        $("#btn-delete").on("click", function () {
            $(".form-check-input-row:checked").closest("tr").remove()
            $(this).hide()
            $("#checkAll").prop("checked", false)
            self.refreshIdx()
        })

        $(".btn-duplicate").on("click", function (e) {
            e.preventDefault()
            // wajib destroy dulu baru duplicate
            let row = $(this).closest("tr");
            row.find("select").select2('destroy');

            let duplicateRow = row.clone(true)
            self.initMoney(duplicateRow.find(".number-format")[0])
            duplicateRow.insertAfter($(this).closest("tr"))

            self.initSelect2(duplicateRow.find("select"))
            self.initSelect2(row.find("select"))

            self.refreshIdx()
        })

        $("#submit-form").on("submit", function (e) {
            e.preventDefault()
            let items = {}
            let formData = new FormData();
            const file_upload = $("#file-upload")[0].files[0]

            formData.append("rfq", "{{ rfq or '' }}")
            formData.append("file_url", file_upload ? file_upload?.name : "")

            let serialize = $(this).serializeArray()
            // console.log(serialize)
            for (let field of serialize) {
                if (field.name.includes("[]")) {
                    let title = field.name.replaceAll("[]", "")
                    items[title] = Array.isArray(items[title]) ? [...items[title], field.value] : [field.value]
                } else if (!Object.hasOwn(self.charges, field.name)) {
                    formData.append(field.name, field.value)
                }
            }

            formData.append("items", JSON.stringify(items))
            formData.append("charges_and_discount", JSON.stringify(self.charges))
            $("#btn-submit").prop("disabled", true)
            $(".loader").show()

            $.ajax({
                url: '/api/method/sth.api.create_sq',
                method: 'POST',
                processData: false,
                contentType: false,
                data: formData,
                headers: {
                    "X-Frappe-CSRF-Token": "{{ csrf_token }}"
                },
                success: function (res) {
                    self.uploadFile(file_upload, res.message.doctype, res.message.docname)
                },
                error: function (err) {
                    if (err.status == 422) {
                        err.responseJSON.message.forEach((row) => {
                            toastr.error(row, "Error")
                        })
                    } else if (err.status == 417) {
                        toastr.error("Form failed to process", "Error")
                    }
                    console.error("Error:", err);
                }
            }).always(() => {
                $("#btn-submit").prop("disabled", false)
                $(".loader").hide()
            });

            //console.log(Object.fromEntries(formData));
        })
    }

}

new FormSupplier()

