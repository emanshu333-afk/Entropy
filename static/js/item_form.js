document.addEventListener("DOMContentLoaded", () => {
    const studentType = document.querySelector("#id_student_type");
    const hostelField = document.querySelector("[data-hostel-field]");
    const hostelSelect = document.querySelector("#id_hostel");
    const genderSelect = document.querySelector("#id_gender");
    const pfpGroups = document.querySelectorAll("[data-pfp-group]");
    const listingTypeInputs = document.querySelectorAll("input[name='listing_type']");
    const priceLabel = document.querySelector("[data-price-label]");
    const photoInput = document.querySelector("#id_photos");
    const uploadCount = document.querySelector("[data-upload-count]");
    const photoPreview = document.querySelector("[data-photo-preview]");
    const form = document.querySelector(".form-card");

    function updateHostelVisibility() {
        const isHosteler = studentType?.value === "hosteler";
        if (!hostelField || !hostelSelect) {
            return;
        }
        hostelField.hidden = !isHosteler;
        hostelSelect.required = isHosteler;
        if (!isHosteler) {
            hostelSelect.value = "";
        }
    }

    function updateProfileOptions() {
        if (!genderSelect || !pfpGroups.length) {
            return;
        }

        const genderValue = (genderSelect.value || '').toLowerCase();
        const visibleGroups = new Set();

        if (['male', 'female', 'other', 'prefer_not_to_say'].includes(genderValue)) {
            visibleGroups.add(genderValue);
            visibleGroups.add('non_binary');
        } else if (genderValue === 'non_binary') {
            visibleGroups.add('non_binary');
        }

        pfpGroups.forEach((group) => {
            const groupKey = group.dataset.pfpGroup;
            const shouldShow = visibleGroups.has(groupKey);
            group.hidden = !shouldShow;
        });

        document.querySelectorAll("input[name='profile_image']").forEach((radio) => {
            const isVisible = radio.dataset.pfpGender && visibleGroups.has(radio.dataset.pfpGender);
            radio.checked = false;
            radio.disabled = !isVisible;
        });

        if (!visibleGroups.size) {
            return;
        }

        const firstAvailableRadio = document.querySelector(
            `input[name='profile_image'][data-pfp-gender='${Array.from(visibleGroups)[0]}']`
        );
        if (firstAvailableRadio) {
            firstAvailableRadio.checked = true;
        }
    }

    function updatePriceLabel() {
        if (!priceLabel) {
            return;
        }
        const selectedType = document.querySelector("input[name='listing_type']:checked")?.value;
        priceLabel.textContent = selectedType === "renting" ? "Rent amount" : "Selling price";
    }

    function updatePhotoPreview() {
        if (!photoInput || !uploadCount || !photoPreview) {
            return;
        }
        const files = [...photoInput.files];
        if (files.length > 4) {
            photoInput.value = "";
            uploadCount.textContent = "Choose up to 4 images";
            photoPreview.replaceChildren();
            return;
        }
        uploadCount.textContent = files.length === 0 ? "No photos selected" : `${files.length} of 4 photos selected`;
        photoPreview.replaceChildren();
        files.forEach((file) => {
            const image = document.createElement("img");
            image.alt = "Selected item photo";
            image.src = URL.createObjectURL(file);
            photoPreview.append(image);
        });
    }

    studentType?.addEventListener("change", updateHostelVisibility);
    genderSelect?.addEventListener("change", updateProfileOptions);
    listingTypeInputs.forEach((input) => input.addEventListener("change", updatePriceLabel));
    photoInput?.addEventListener("change", updatePhotoPreview);
    form?.addEventListener("submit", (event) => {
        if (photoInput && photoInput.files.length > 4) {
            event.preventDefault();
            uploadCount.textContent = "Choose up to 4 images";
        }
        if (studentType?.value === "hosteler" && !hostelSelect?.value) {
            event.preventDefault();
            hostelSelect?.focus();
        }
    });

    updateHostelVisibility();
    updateProfileOptions();
    updatePriceLabel();
    updatePhotoPreview();
});
