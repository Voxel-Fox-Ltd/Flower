async function waterPlant(object) {
    while(!object.classList.contains("plant")) object = object.parentNode;

    // Get the relevant information
    let plantName = object.getElementsByClassName("title")[0].textContent;
    let progressBar = object.getElementsByClassName("progress")[0];
    let nourishmentNode = object.getElementsByClassName("nourishment")[0];

    // Set up the progress bar
    let currentProgressBarValue = progressBar.getAttribute("value");
    progressBar.setAttribute("value", "");

    // Perform our API request
    let jsonData = JSON.stringify({plant_name: plantName});
    console.log(`Sending data to /water_plant: ${jsonData}`);
    let data = await fetch("/water_plant", {
        method: "POST",
        body: jsonData,
        headers: {"Content-Type": "application/json"}
    })
    let response = await data.json()
    console.log(`Received response from /water_plant: ${JSON.stringify(response)}`);

    // Set the progress bar back to what it was if nothing has changed
    if (!response.success) {
        progressBar.setAttribute("value", currentProgressBarValue);
        return;
    }

    // Update the progress bar
    document.getElementById("experience").innerHTML = Math.max(parseInt(document.getElementById("experience").innerHTML), response.new_user_experience);
    progressBar.setAttribute("value", response.new_nourishment_level / 21);
    nourishmentNode.innerHTML = response.new_nourishment_level;

    // Update the flower image
    // TODO
}


async function deletePlant(object) {
    while(!object.classList.contains("plant")) object = object.parentNode;

    // Get the relevant information
    let plantName = object.getElementsByClassName("title")[0].textContent;

    // Perform our API request
    let jsonData = JSON.stringify({plant_name: plantName});
    console.log(`Sending data to /delete_plant: ${jsonData}`);
    let data = await fetch("/delete_plant", {
        method: "POST",
        body: jsonData,
        headers: {"Content-Type": "application/json"}
    })
    let response = await data.json()
    console.log(`Received response from /delete_plant: ${JSON.stringify(response)}`);
    return response.success;
}


async function revivePlant(object) {
    while(!object.classList.contains("plant")) object = object.parentNode;
    alert("Currently non-functional - please run the revive command from Discord.");
}


async function deletePlantDom(object) {
    while(!object.classList.contains("plant")) object = object.parentNode;
    object.remove();
}


async function unhideDeleteModal(object) {
    while(!object.classList.contains("plant")) object = object.parentNode;
    let modal = object.getElementsByClassName("modal")[0];
    modal.classList.add("is-active");
    let deleteButton = object.getElementsByClassName("delete-button")[0];
    setTimeout(function() {
        deleteButton.disabled = false;
    }, 1_000);
}


async function hideDeleteModal(object) {
    while(!object.classList.contains("plant")) object = object.parentNode;
    let modal = object.getElementsByClassName("modal")[0];
    modal.classList.remove("is-active");
    let deleteButton = object.getElementsByClassName("delete-button")[0];
    deleteButton.disabled = true;
}
