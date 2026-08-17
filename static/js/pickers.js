// Single-box pickers: customer and product on the sale form, category on
// the expense form. Any form can use one — see templates/partials/pickers.html.
//
// Each picker is one control: click it and the list drops down, type and it
// narrows, pick a row and it closes. The chosen id travels in a hidden input
// under the original field name, so the server side is unchanged.
//
// Also runs the "+ New" dialogs, which create a customer or product without
// throwing away the half-filled order on screen.

(function () {
  const OPEN_CLASS = "combo-open";

  let comboSeq = 0;

  function itemsOf(combo) {
    return Array.prototype.slice.call(combo.querySelectorAll(".combo-option"));
  }

  function isCreateRow(item) {
    return Boolean(item) && item.classList.contains("combo-create");
  }

  // Real records only — the "+ New ..." row is not one of them.
  function recordsOf(combo) {
    return itemsOf(combo).filter(function (li) {
      return !isCreateRow(li);
    });
  }

  function visibleItems(combo) {
    return itemsOf(combo).filter(function (li) {
      return !li.hidden;
    });
  }

  // What Enter should pick when the user has not arrowed anywhere. The
  // "+ New ..." row sits at the top of the list, but a real match always
  // wins over it — otherwise typing "pack" would offer to create a second
  // "Packaging" rather than select the one that exists.
  function firstChoice(combo) {
    const visible = visibleItems(combo);
    const record = visible.find(function (li) {
      return !isCreateRow(li);
    });
    return record || visible[0] || null;
  }

  function labelOf(item) {
    return item.textContent.trim();
  }

  function close(combo) {
    combo.classList.remove(OPEN_CLASS);
    combo.querySelector(".combo-list").hidden = true;
    setActive(combo, null);
  }

  function open(combo) {
    // Only one picker open at a time, otherwise two lists overlap.
    document.querySelectorAll("." + OPEN_CLASS).forEach(function (other) {
      if (other !== combo) close(other);
    });
    combo.classList.add(OPEN_CLASS);
    combo.querySelector(".combo-list").hidden = false;
  }

  function setActive(combo, item) {
    itemsOf(combo).forEach(function (li) {
      li.classList.toggle("is-active", li === item);
    });
    if (item && item.scrollIntoView) {
      item.scrollIntoView({ block: "nearest" });
    }
  }

  function filter(combo, query) {
    const term = (query || "").trim();
    const needle = term.toLowerCase();
    let shown = 0;

    recordsOf(combo).forEach(function (li) {
      const match = !needle || labelOf(li).toLowerCase().indexOf(needle) !== -1;
      li.hidden = !match;
      if (match) shown++;
    });

    // The create row is never filtered out — it is the way out when nothing
    // matches — but it does say what it will create.
    const create = combo.querySelector(".combo-create");
    if (create) {
      const kind = create.dataset.create;
      create.textContent = term ? '+ Add "' + term + '" as a new ' + kind : "+ New " + kind;
      create.dataset.term = term;
      create.classList.toggle("is-only-option", shown === 0);
    }
    return shown;
  }

  function choose(combo, item) {
    if (isCreateRow(item)) {
      startCreate(combo, item.dataset.term || "");
      return;
    }

    const input = combo.querySelector(".combo-input");
    const hidden = combo.querySelector(".combo-value");

    hidden.value = item ? item.dataset.value : "";
    input.value = item ? labelOf(item) : "";
    // Carry the price along for the row's autofill to read.
    if (item && item.dataset.price !== undefined) {
      hidden.dataset.price = item.dataset.price;
    } else {
      delete hidden.dataset.price;
    }
    combo.classList.toggle("has-value", Boolean(hidden.value));
    clearError(combo);
    close(combo);
    hidden.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function selectedItem(combo) {
    const hidden = combo.querySelector(".combo-value");
    if (!hidden.value) return null;
    return combo.querySelector('.combo-option[data-value="' + hidden.value + '"]');
  }

  // Typing something that was never picked would leave a label with no id
  // behind, so put the real selection back whenever the box loses focus.
  function restoreLabel(combo) {
    const input = combo.querySelector(".combo-input");
    const current = selectedItem(combo);
    input.value = current ? labelOf(current) : "";
  }

  function showError(combo, message) {
    const error = combo.parentElement.querySelector(".combo-error");
    if (error) error.textContent = message;
    combo.classList.add("has-error");
  }

  function clearError(combo) {
    const error = combo.parentElement.querySelector(".combo-error");
    if (error) error.textContent = "";
    combo.classList.remove("has-error");
  }

  function initCombo(combo) {
    if (!combo || combo.dataset.comboReady === "1") return;
    combo.dataset.comboReady = "1";

    const input = combo.querySelector(".combo-input");
    const hidden = combo.querySelector(".combo-value");
    combo.classList.toggle("has-value", Boolean(hidden.value));

    input.addEventListener("focus", function () {
      filter(combo, "");
      open(combo);
    });

    input.addEventListener("input", function () {
      filter(combo, input.value);
      open(combo);
      setActive(combo, firstChoice(combo));
    });

    input.addEventListener("keydown", function (e) {
      const items = visibleItems(combo);
      const active = combo.querySelector(".combo-option.is-active");
      const index = items.indexOf(active);

      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!combo.classList.contains(OPEN_CLASS)) open(combo);
        const step = e.key === "ArrowDown" ? 1 : -1;
        const next = items[(index + step + items.length) % (items.length || 1)];
        setActive(combo, next || null);
      } else if (e.key === "Enter") {
        if (combo.classList.contains(OPEN_CLASS)) {
          // Don't submit the order just because a picker was open.
          e.preventDefault();
          choose(combo, active || firstChoice(combo));
        }
      } else if (e.key === "Escape") {
        restoreLabel(combo);
        close(combo);
      }
    });

    combo.querySelector(".combo-list").addEventListener("mousedown", function (e) {
      // mousedown, not click: blur would close the list first.
      const item = e.target.closest(".combo-option");
      if (item) {
        e.preventDefault();
        choose(combo, item);
      }
    });

    combo.querySelector(".combo-toggle").addEventListener("mousedown", function (e) {
      e.preventDefault();
      if (combo.classList.contains(OPEN_CLASS)) {
        close(combo);
      } else {
        input.focus();
      }
    });

    input.addEventListener("blur", function () {
      // Let a click on the list land before tidying up.
      window.setTimeout(function () {
        if (!combo.contains(document.activeElement)) {
          restoreLabel(combo);
          close(combo);
        }
      }, 0);
    });
  }

  function initAll(root) {
    (root || document).querySelectorAll("[data-combo]").forEach(initCombo);
  }

  // A cloned product row arrives carrying whatever the source row had
  // picked and however its list was filtered — give it a clean one.
  function prepareClonedRow(root) {
    root.querySelectorAll("[data-combo]").forEach(function (combo) {
      delete combo.dataset.comboReady;
      combo.querySelector(".combo-input").value = "";
      const hidden = combo.querySelector(".combo-value");
      hidden.value = "";
      delete hidden.dataset.price;
      combo.classList.remove("has-value", "has-error", OPEN_CLASS);
      combo.querySelector(".combo-list").hidden = true;
      filter(combo, "");
      initCombo(combo);
    });
  }

  // Put a newly created record into every picker of that kind, so a new
  // product is available on all order rows, not just the one in front of you.
  function addOption(kind, value, label, price) {
    document.querySelectorAll('[data-combo="' + kind + '"]').forEach(function (combo) {
      const list = combo.querySelector(".combo-list");
      const item = document.createElement("li");
      item.className = "combo-option";
      item.dataset.value = value;
      if (price !== undefined && price !== null) item.dataset.price = price;
      item.textContent = label;
      // The "+ New ..." row stays at the top, so records go on the end.
      list.appendChild(item);
      filter(combo, combo.querySelector(".combo-input").value);
    });
  }

  /* ---------- creating from inside the picker ---------- */

  // Each kind's dialog is found by convention — "category" -> newCategoryDialog
  // — so a new picker needs no change here, only a dialog in the template.
  function dialogFor(kind) {
    const id = "new" + kind.charAt(0).toUpperCase() + kind.slice(1) + "Dialog";
    return document.getElementById(id);
  }

  // The "+ Add ..." row opens the small form with the name already typed in,
  // so nothing is retyped and the order on screen is left alone.
  function startCreate(combo, term) {
    const kind = combo.dataset.combo;
    const dialog = dialogFor(kind);
    if (!dialog) return;

    // Product rows have no id of their own; give one so the created record
    // can be dropped back into the exact row that asked for it.
    if (!combo.id) combo.id = "combo-" + kind + "-" + ++comboSeq;

    close(combo);
    openDialog(dialog, combo.id);

    const nameField = dialog.querySelector("[data-field='name']");
    if (nameField) {
      nameField.value = term;
      nameField.focus();
      nameField.select();
    }
  }

  function openDialog(dialog, targetCombo) {
    dialog.hidden = false;
    dialog.dataset.target = targetCombo || "";
    const error = dialog.querySelector(".dialog-error");
    if (error) error.textContent = "";
    const first = dialog.querySelector("input");
    if (first) first.focus();
  }

  function closeDialog(dialog) {
    dialog.hidden = true;
    dialog.querySelectorAll("input").forEach(function (input) {
      input.value = "";
    });
  }

  function submitDialog(dialog) {
    const kind = dialog.dataset.dialog; // "customer" or "product"
    const error = dialog.querySelector(".dialog-error");
    const saveBtn = dialog.querySelector(".dialog-save");
    const body = new FormData();

    dialog.querySelectorAll("[data-field]").forEach(function (input) {
      body.append(input.dataset.field, input.value);
    });

    saveBtn.disabled = true;
    error.textContent = "";

    fetch(dialog.dataset.url, { method: "POST", body: body })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok || !result.data.ok) {
          error.textContent = result.data.error || "Could not save. Please try again.";
          return;
        }

        const record = result.data[kind];
        const label =
          kind === "customer" && record.phone
            ? record.name + " (" + record.phone + ")"
            : record.name;
        addOption(kind, String(record.id), label, record.selling_price);

        // Drop it straight into a picker: the one that opened the dialog,
        // or else the first row still waiting for a product.
        let combo = dialog.dataset.target
          ? document.getElementById(dialog.dataset.target)
          : null;
        if (!combo) {
          combo = Array.prototype.find.call(
            document.querySelectorAll('[data-combo="' + kind + '"]'),
            function (candidate) {
              return !candidate.querySelector(".combo-value").value;
            }
          );
        }
        if (combo) {
          const added = combo.querySelector(
            '.combo-option[data-value="' + record.id + '"]'
          );
          if (added) choose(combo, added);
        }
        closeDialog(dialog);
      })
      .catch(function () {
        error.textContent = "Could not reach the server. Check the app is still running.";
      })
      .finally(function () {
        saveBtn.disabled = false;
      });
  }

  /* ---------- submit guard ---------- */

  // The real field is a hidden input, which browsers never validate, so the
  // "please choose one" check lives here. The server checks again anyway.
  function validateForm(form) {
    let firstBad = null;
    form.querySelectorAll("[data-combo][data-required]").forEach(function (combo) {
      if (combo.querySelector(".combo-value").value) {
        clearError(combo);
        return;
      }
      showError(combo, combo.dataset.requiredMessage || "Please choose one.");
      if (!firstBad) firstBad = combo;
    });

    if (firstBad) {
      firstBad.querySelector(".combo-input").focus();
      return false;
    }
    return true;
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAll(document);

    // Guard every form that contains a required picker, not one named form,
    // so a picker dropped onto a new page is checked without extra wiring.
    const guarded = new Set();
    document.querySelectorAll("[data-combo][data-required]").forEach(function (combo) {
      const form = combo.closest("form");
      if (!form || guarded.has(form)) return;
      guarded.add(form);
      form.addEventListener("submit", function (e) {
        if (!validateForm(form)) e.preventDefault();
      });
    });

    document.addEventListener("click", function (e) {
      if (!e.target.closest) return;

      const opener = e.target.closest("[data-open-dialog]");
      if (opener) {
        const dialog = document.getElementById(opener.dataset.openDialog);
        if (dialog) openDialog(dialog, opener.dataset.targetCombo);
        return;
      }
      if (e.target.closest(".dialog-cancel")) {
        closeDialog(e.target.closest("[data-dialog]"));
        return;
      }
      if (e.target.closest(".dialog-save")) {
        submitDialog(e.target.closest("[data-dialog]"));
        return;
      }
      // A click anywhere else shuts an open picker.
      if (!e.target.closest("[data-combo]")) {
        document.querySelectorAll("." + OPEN_CLASS).forEach(function (combo) {
          restoreLabel(combo);
          close(combo);
        });
      }
    });

    document.addEventListener("keydown", function (e) {
      if (!e.target.closest) return;
      const dialog = e.target.closest("[data-dialog]");
      if (!dialog || dialog.hidden) return;
      if (e.key === "Enter") {
        e.preventDefault();
        submitDialog(dialog);
      } else if (e.key === "Escape") {
        closeDialog(dialog);
      }
    });
  });

  // sales_form.js calls these when it adds a product row.
  window.initSalePickers = initAll;
  window.prepareClonedSaleRow = prepareClonedRow;
})();
