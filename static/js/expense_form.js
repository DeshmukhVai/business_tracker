// The optional raw-material rows on the Add/Edit Expense form.
//
// These rows are a reference note of what individual things cost. Nothing
// here calculates anything: no per-row subtotal, no items total, and the
// Total Amount field is never touched — that figure is whatever the owner
// typed. This file only adds and removes rows.

document.addEventListener("DOMContentLoaded", function () {
  const body = document.getElementById("expenseItemsBody");
  const addRowBtn = document.getElementById("addItemRowBtn");

  if (!body) return;

  function blankRow() {
    const clone = body.querySelector(".expense-item-row").cloneNode(true);
    clone.querySelectorAll("input").forEach((el) => {
      el.value = el.classList.contains("item-qty") ? 1 : "";
    });
    return clone;
  }

  body.addEventListener("click", function (e) {
    if (!e.target.classList.contains("remove-item-row")) return;

    const rows = body.querySelectorAll(".expense-item-row");
    if (rows.length > 1) {
      e.target.closest(".expense-item-row").remove();
    } else {
      // Keep one row on screen so the section never disappears; clearing
      // it is how you end up with no items at all.
      rows[0].querySelectorAll("input").forEach((el) => {
        el.value = el.classList.contains("item-qty") ? 1 : "";
      });
    }
  });

  if (addRowBtn) {
    addRowBtn.addEventListener("click", function () {
      body.appendChild(blankRow());
    });
  }
});
