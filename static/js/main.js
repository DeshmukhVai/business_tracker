// Sidebar toggle for mobile
document.addEventListener("DOMContentLoaded", function () {
  const toggle = document.getElementById("menuToggle");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");

  if (toggle && sidebar && overlay) {
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("open");
      overlay.classList.toggle("open");
    });
    overlay.addEventListener("click", function () {
      sidebar.classList.remove("open");
      overlay.classList.remove("open");
    });
  }

  // Auto-hide flash messages after a few seconds.
  document.querySelectorAll(".flash").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 400);
    }, 4000);
  });

  // Generic "confirm before delete" for any form with data-confirm.
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!confirm(form.getAttribute("data-confirm"))) {
        e.preventDefault();
      }
    });
  });

  // Filter bars: picking a dropdown value or a date applies the filter
  // right away, the same way the Products "show inactive" checkbox
  // already does — no need to also find and click the search button.
  document.querySelectorAll(".filter-bar select, .filter-bar input[type='date']").forEach(function (el) {
    el.addEventListener("change", function () {
      el.form.submit();
    });
  });

  registerLiveSearch();
  registerClickableRows();
  registerBusinessSwitcher();
});

// Search boxes in a filter bar apply as you type, pausing briefly after
// the last keystroke first — these pages reload the whole page rather
// than fetching results over AJAX, so submitting on every single
// keystroke would reload mid-word and fight with what's still being
// typed. The short pause is what keeps it feeling live without that.
//
// A side effect of reloading the page is that the box itself is
// recreated and loses focus, so after the reload this also puts focus
// back in it (cursor at the end) — see restoreLiveSearchFocus() below.
const LIVE_SEARCH_DEBOUNCE_MS = 450;
const LIVE_SEARCH_REFOCUS_KEY = "liveSearchRefocusField";

function registerLiveSearch() {
  document.querySelectorAll(".filter-bar input[type='text']").forEach(function (el) {
    let timer = null;
    el.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        try {
          sessionStorage.setItem(LIVE_SEARCH_REFOCUS_KEY, el.name);
        } catch (err) {
          // Private-browsing or a blocked storage API — the filter still
          // applies, it just won't refocus itself afterwards.
        }
        el.form.submit();
      }, LIVE_SEARCH_DEBOUNCE_MS);
    });
  });

  restoreLiveSearchFocus();
}

function restoreLiveSearchFocus() {
  let name;
  try {
    name = sessionStorage.getItem(LIVE_SEARCH_REFOCUS_KEY);
    sessionStorage.removeItem(LIVE_SEARCH_REFOCUS_KEY);
  } catch (err) {
    return;
  }
  if (!name) return;

  const field = document.querySelector(".filter-bar input[type='text'][name='" + name + "']");
  if (!field) return;
  field.focus();
  // Re-assigning the value moves the caret to the end, rather than
  // leaving it at the start where a freshly-focused field defaults to.
  const value = field.value;
  field.value = "";
  field.value = value;
}

// Sidebar business switcher: picking a different business posts straight
// to its switch endpoint. The URL template carries a placeholder id (0)
// baked in by the server via url_for, so the path itself never needs to
// be known here.
function registerBusinessSwitcher() {
  const form = document.getElementById("businessSwitchForm");
  const select = document.getElementById("businessSwitchSelect");
  if (!form || !select) return;

  select.addEventListener("change", function () {
    if (!select.value) return; // the disabled placeholder can't really be chosen, but just in case
    const template = form.getAttribute("data-switch-url-template");
    form.action = template.replace("/0/switch", "/" + select.value + "/switch");
    form.submit();
  });
}

// Rows carrying data-href open that record when clicked anywhere, so the
// whole line is a target instead of just the small View button.
//
// Delegated from the document so it covers every table on every page,
// including rows added after load.
function registerClickableRows() {
  document.addEventListener("click", function (e) {
    const href = rowTarget(e);
    if (!href) return;
    // Cmd/Ctrl-click opens a new tab, the way a real link would.
    if (e.metaKey || e.ctrlKey || e.shiftKey) {
      window.open(href, "_blank");
    } else {
      window.location.href = href;
    }
  });

  // Middle-click fires auxclick rather than click.
  document.addEventListener("auxclick", function (e) {
    if (e.button !== 1) return;
    const href = rowTarget(e);
    if (href) window.open(href, "_blank");
  });
}

// The record a click should open, or null if this click belongs to
// something else.
function rowTarget(e) {
  const row = e.target.closest("tr[data-href]");
  if (!row) return null;

  // Controls inside the row keep doing their own job — the action
  // buttons, the delete form, the "+N more" link.
  if (e.target.closest("a, button, input, select, textarea, label, form")) {
    return null;
  }

  // Dragging across a row to copy an amount ends in a click. Navigating
  // then would throw away the selection the user just made.
  const selection = window.getSelection();
  if (selection && !selection.isCollapsed) return null;

  return row.getAttribute("data-href");
}
