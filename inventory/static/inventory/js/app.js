(() => {
    "use strict";

    const root = document.documentElement;
    root.classList.remove("no-js");
    root.classList.add("js");

    const initFilterPanels = () => {
        document.querySelectorAll("[data-filter-panel]").forEach((panel) => {
            panel.classList.add("collapse");
            if (panel.dataset.expanded === "true") {
                panel.classList.add("show");
            }
        });
    };

    const initNavigation = () => {
        const navigation = document.querySelector("#primary-navigation");
        const trigger = document.querySelector('[data-bs-target="#primary-navigation"]');

        if (!navigation || !trigger) {
            return;
        }

        navigation.addEventListener("show.bs.offcanvas", () => {
            trigger.setAttribute("aria-expanded", "true");
            trigger.setAttribute("aria-label", "Close navigation");
        });

        navigation.addEventListener("hidden.bs.offcanvas", () => {
            trigger.setAttribute("aria-expanded", "false");
            trigger.setAttribute("aria-label", "Open navigation");
            if (trigger.offsetParent !== null) {
                trigger.focus();
            }
        });
    };

    const initInvalidFields = () => {
        document.querySelectorAll(".has-errors .field-feedback").forEach((feedback) => {
            feedback.setAttribute("role", "alert");
        });

        const firstInvalid = document.querySelector(
            '.has-errors [aria-invalid="true"], .has-errors input, .has-errors select, .has-errors textarea'
        );

        if (firstInvalid) {
            window.requestAnimationFrame(() => {
                firstInvalid.focus({ preventScroll: true });
                const reducedMotion = window.matchMedia(
                    "(prefers-reduced-motion: reduce)"
                ).matches;
                firstInvalid.scrollIntoView({
                    behavior: reducedMotion ? "auto" : "smooth",
                    block: "center",
                });
            });
        }
    };

    const resetSubmitState = (form) => {
        const button = form.querySelector("[data-submit-button]");
        if (!button) {
            return;
        }

        const label = button.querySelector("[data-submit-label]");
        const spinner = button.querySelector("[data-submit-spinner]");
        if (label && button.dataset.idleLabel) {
            label.textContent = button.dataset.idleLabel;
        }
        if (spinner) {
            spinner.classList.add("d-none");
        }
        button.disabled = false;
        form.removeAttribute("aria-busy");
    };

    const initSubmitStates = () => {
        document.querySelectorAll("[data-submit-form]").forEach((form) => {
            const button = form.querySelector("[data-submit-button]");
            if (!button) {
                return;
            }

            const label = button.querySelector("[data-submit-label]");
            if (label) {
                button.dataset.idleLabel = label.textContent.trim();
            }

            form.addEventListener("submit", () => {
                if (!form.checkValidity()) {
                    return;
                }

                form.setAttribute("aria-busy", "true");
                button.disabled = true;
                if (label && button.dataset.busyLabel) {
                    label.textContent = button.dataset.busyLabel;
                }
                const spinner = button.querySelector("[data-submit-spinner]");
                if (spinner) {
                    spinner.classList.remove("d-none");
                }
            });
        });

        window.addEventListener("pageshow", () => {
            document.querySelectorAll("[data-submit-form]").forEach(resetSubmitState);
        });
    };

    const formState = (form) => JSON.stringify(
        Array.from(form.elements)
            .filter((control) => control.name && control.name !== "csrfmiddlewaretoken")
            .map((control) => [
                control.name,
                control.type === "checkbox" || control.type === "radio" ? control.checked : control.value,
            ])
    );

    const initDirtyGuards = () => {
        const dirtyForms = new Set();

        document.querySelectorAll("[data-dirty-guard]").forEach((form) => {
            const initialState = formState(form);
            const updateState = () => {
                if (formState(form) === initialState) {
                    dirtyForms.delete(form);
                } else {
                    dirtyForms.add(form);
                }
            };

            form.addEventListener("input", updateState);
            form.addEventListener("change", updateState);
            form.addEventListener("submit", () => {
                if (form.checkValidity()) {
                    dirtyForms.delete(form);
                }
            });

            form.querySelectorAll("[data-cancel-form]").forEach((cancel) => {
                cancel.addEventListener("click", () => dirtyForms.delete(form));
            });
        });

        window.addEventListener("beforeunload", (event) => {
            if (dirtyForms.size === 0) {
                return;
            }
            event.preventDefault();
            event.returnValue = "";
        });
    };

    const initPasswordToggles = () => {
        document.querySelectorAll("[data-password-toggle]").forEach((button) => {
            const input = document.getElementById(button.getAttribute("aria-controls"));
            if (!input) {
                return;
            }

            button.addEventListener("click", () => {
                const isVisible = input.type === "text";
                input.type = isVisible ? "password" : "text";
                button.setAttribute("aria-pressed", String(!isVisible));
                button.textContent = isVisible ? "Show" : "Hide";
            });
        });
    };

    initFilterPanels();
    initNavigation();
    initInvalidFields();
    initSubmitStates();
    initDirtyGuards();
    initPasswordToggles();
})();
