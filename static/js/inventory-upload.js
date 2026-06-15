// Wires the /inventory/ upload bucket: drag-and-drop and picker selection both
// submit the existing form. Without this, dropped files open in the browser and
// picked files do nothing (the submit button is hidden, no change handler).
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  ready(function () {
    var form = document.querySelector("#bucket form");
    var input = document.getElementById("bucket-input");
    var dropzone = document.getElementById("bucket-dropzone");
    var addBtn = document.getElementById("add-policies");

    // Active-run state renders a disabled input and no submit button. Do not
    // wire uploads in that state.
    var uploadable = form && input && !input.disabled;

    // Prevent the browser from navigating to / opening a file dropped anywhere
    // on the page. This is the fix for "drag-and-drop opens the PDF in Chrome".
    function stop(e) {
      e.preventDefault();
      e.stopPropagation();
    }
    ["dragover", "drop"].forEach(function (evt) {
      window.addEventListener(evt, stop, false);
    });

    if (!uploadable) {
      return;
    }

    // "Add policies" opens the native picker instead of only scrolling.
    if (addBtn) {
      addBtn.addEventListener("click", function (e) {
        e.preventDefault();
        input.click();
      });
    }

    // Picker selection submits immediately.
    input.addEventListener("change", function () {
      if (input.files && input.files.length > 0) {
        form.requestSubmit();
      }
    });

    if (dropzone) {
      dropzone.addEventListener("dragenter", function () {
        dropzone.classList.add("border-primary", "bg-base-200");
      });
      dropzone.addEventListener("dragleave", function (e) {
        // Ignore dragleave bubbling up from child spans.
        if (e.target === dropzone) {
          dropzone.classList.remove("border-primary", "bg-base-200");
        }
      });
      dropzone.addEventListener("drop", function (e) {
        dropzone.classList.remove("border-primary", "bg-base-200");
        var dropped = e.dataTransfer && e.dataTransfer.files;
        if (dropped && dropped.length > 0) {
          input.files = dropped;
          form.requestSubmit();
        }
      });
    }
  });
})();
