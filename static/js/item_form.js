document.addEventListener('DOMContentLoaded', () => {
    const priceInput = document.querySelector('#price');
    const listingTypeInputs = document.querySelectorAll('input[name="listing_type"]');

    if (!priceInput || listingTypeInputs.length === 0) return;

    const updatePriceLabel = () => {
        const selected = document.querySelector('input[name="listing_type"]:checked');
        const type = selected ? selected.value : 'sell';
        priceInput.placeholder = type === 'rent' ? 'Enter monthly rent' : 'Enter selling price';
    };

    listingTypeInputs.forEach((input) => {
        input.addEventListener('change', updatePriceLabel);
    });

    updatePriceLabel();
});
