// Submits the /inventory/ upload form on picker selection and on drop. The form
// has no visible submit button, so without this JS there is no way to upload.
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

    // Prevent the browser from opening a file dropped anywhere on the page.
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

    // A large upload stays in flight for seconds; a second submit would abort
    // the first navigation and discard it. Submit at most once.
    var submitting = false;
    function submit() {
      if (submitting) {
        return;
      }
      submitting = true;
      form.requestSubmit();
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
        submit();
      }
    });

    if (dropzone) {
      // dragenter/dragleave both fire when crossing into child elements; a
      // depth counter keeps the highlight steady until the cursor truly leaves.
      var dragDepth = 0;
      function highlight(on) {
        if (on) {
          dropzone.classList.add("border-primary", "bg-base-200");
        } else {
          dropzone.classList.remove("border-primary", "bg-base-200");
        }
      }
      dropzone.addEventListener("dragenter", function () {
        dragDepth += 1;
        highlight(true);
      });
      dropzone.addEventListener("dragleave", function () {
        dragDepth -= 1;
        if (dragDepth <= 0) {
          dragDepth = 0;
          highlight(false);
        }
      });
      dropzone.addEventListener("drop", function (e) {
        dragDepth = 0;
        highlight(false);
        var dropped = e.dataTransfer && e.dataTransfer.files;
        if (dropped && dropped.length > 0) {
          input.files = dropped;
          submit();
        }
      });
    }
  });
})();
