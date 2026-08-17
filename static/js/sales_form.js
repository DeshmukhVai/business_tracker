// Handles the dynamic product line-items table on the Add/Edit Sale form:
// auto-fills selling price when a product is chosen, recalculates each
// row's subtotal and the overall order total, and lets the user add or
// remove product rows without a page reload.

document.addEventListener("DOMContentLoaded", function () {
  const body = document.getElementById("lineItemsBody");
  const addRowBtn = document.getElementById("addRowBtn");
  const discountInput = document.getElementById("discountInput");
  const discountTypeToggle = document.getElementById("discountTypeToggle");
  const discountHint = document.getElementById("discountHint");
  const subtotalHint = document.getElementById("subtotalHint");
  const orderTotalDisplay = document.getElementById("orderTotalDisplay");
  const amountPaidInput = document.getElementById("amountPaidInput");
  const paymentStatusPreview = document.getElementById("paymentStatusPreview");

  if (!body) return;

  function templateRow() {
    const firstRow = body.querySelector(".line-item-row");
    const clone = firstRow.cloneNode(true);
    clone.querySelectorAll("select, input").forEach((el) => {
      if (el.classList.contains("qty-input")) {
        el.value = 1;
      } else if (el.tagName === "SELECT") {
        el.value = "";
      } else {
        el.value = "";
      }
    });
    clone.querySelector(".subtotal-cell").textContent = "0.00";
    // Give the new row the unfiltered product list and its own search box.
    if (window.prepareClonedSaleRow) window.prepareClonedSaleRow(clone);
    return clone;
  }

  function recalcRow(row) {
    const qty = parseFloat(row.querySelector(".qty-input").value) || 0;
    const price = parseFloat(row.querySelector(".price-input").value) || 0;
    const subtotal = qty * price;
    row.querySelector(".subtotal-cell").textContent = subtotal.toFixed(2);
    return subtotal;
  }

  function discountType() {
    const checked = document.querySelector("input[name='discount_type']:checked");
    return checked ? checked.value : "amount";
  }

  // Mirrors Sale.compute_discount on the server, which recalculates this
  // independently — the browser figure is a preview, not the source.
  function discountAmount(itemsTotal) {
    const value = parseFloat(discountInput.value) || 0;
    const amount = discountType() === "percent" ? (itemsTotal * value) / 100 : value;
    return Math.min(Math.max(amount, 0), itemsTotal);
  }

  // Preview of the badge the order will get. The status itself is always
  // derived on the server from amount_paid vs total_amount — this just
  // shows the outcome before saving.
  function updatePaymentPreview(orderTotal) {
    if (!paymentStatusPreview || !amountPaidInput) return;

    const raw = amountPaidInput.value.trim();
    if (raw === "") {
      paymentStatusPreview.textContent = "";
      paymentStatusPreview.className = "status-preview";
      return;
    }

    const paid = parseFloat(raw) || 0;
    let badge = "badge-pending";
    let text = "Pending — nothing received yet";

    if (orderTotal <= 0) {
      badge = "badge-paid";
      text = "Paid — nothing to collect";
    } else if (paid > orderTotal) {
      badge = "badge-pending";
      text = "More than the order total of " + orderTotal.toFixed(2);
    } else if (paid >= orderTotal) {
      badge = "badge-paid";
      text = "Paid in full";
    } else if (paid > 0) {
      badge = "badge-partial";
      text = "Partially Paid — " + (orderTotal - paid).toFixed(2) + " still due";
    }

    paymentStatusPreview.className = "status-preview badge " + badge;
    paymentStatusPreview.textContent = text;
  }

  function recalcTotal() {
    let total = 0;
    body.querySelectorAll(".line-item-row").forEach((row) => {
      total += recalcRow(row);
    });

    const discount = discountAmount(total);
    orderTotalDisplay.value = Math.max(total - discount, 0).toFixed(2);

    if (subtotalHint) {
      subtotalHint.textContent = "Items subtotal " + total.toFixed(2);
    }
    updatePaymentPreview(Math.max(total - discount, 0));

    if (discountHint) {
      if (discount > 0 && discountType() === "percent") {
        discountHint.textContent = "= " + discount.toFixed(2) + " off";
      } else if (discountType() === "percent") {
        discountHint.textContent = "Percentage of the items subtotal.";
      } else {
        discountHint.textContent = "Flat amount off the order.";
      }
    }
  }

  body.addEventListener("change", function (e) {
    // The picker is a combobox now: the chosen product's price rides along
    // on the hidden input as data-price.
    if (e.target.classList.contains("product-select")) {
      const price = e.target.dataset.price;
      const row = e.target.closest(".line-item-row");
      const priceInput = row.querySelector(".price-input");
      if (price) {
        priceInput.value = price;
      }
      recalcTotal();
    }
  });

  body.addEventListener("input", function (e) {
    if (e.target.classList.contains("qty-input") || e.target.classList.contains("price-input")) {
      recalcTotal();
    }
  });

  body.addEventListener("click", function (e) {
    if (e.target.classList.contains("remove-row")) {
      const rows = body.querySelectorAll(".line-item-row");
      if (rows.length > 1) {
        e.target.closest(".line-item-row").remove();
        recalcTotal();
      }
    }
  });

  if (addRowBtn) {
    addRowBtn.addEventListener("click", function () {
      body.appendChild(templateRow());
    });
  }

  discountInput.addEventListener("input", recalcTotal);
  if (amountPaidInput) amountPaidInput.addEventListener("input", recalcTotal);

  if (discountTypeToggle) {
    discountTypeToggle.addEventListener("change", function () {
      // A percentage is capped at 100, a rupee amount is not.
      discountInput.max = discountType() === "percent" ? 100 : "";
      recalcTotal();
    });
  }

  recalcTotal();
});
