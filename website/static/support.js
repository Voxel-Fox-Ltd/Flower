async function updateDisplayText(input) {
    let value = input.value;
    let expAmount = document.getElementById("exp-amount");
    let price = document.getElementById("money-amount");
    expAmount.innerHTML = (parseInt(expAmount.dataset.original) * value).toLocaleString('en-US', {minimumFractionDigits: 0});
    price.innerHTML = (parseInt(price.dataset.original) * value).toLocaleString('en-US', {minimumFractionDigits: 2});
}
