async function waterPlant(object) {
    while(!object.classList.contains("plant")) object = object.parentNode;

    // Get the relevant information
    let plantName = object.getElementsByClassName("title")[0].textContent;
    let progressBar = object.getElementsByClassName("nourishment-progress")[0];
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

    // Disable the water button
    let waterButton = object.getElementsByClassName("water-button")[0];
    waterButton.disabled = true;
    enablePlantWaterButton(object, waterButton.dataset.baseDisableTime)

    // Update the flower image
    // TODO
}


async function setupWaterButtonTimeout() {
    let waterButtons = document.getElementsByClassName("water-button");
    for(let wb of waterButtons) {
        enablePlantWaterButton(wb, wb.dataset.disableTime);
    }
}


async function enablePlantWaterButton(object, sleepTime) {
    while(!object.classList.contains("plant")) object = object.parentNode;
    let waterButton = object.getElementsByClassName("water-button")[0];
    let plantName = object.getElementsByClassName("title")[0].textContent;
    let progressBar = object.getElementsByClassName("water-progress")[0];
    if(sleepTime > 0) progressBar.value = 0;
    console.log(`Sleeping for ${sleepTime} seconds before enabling water button for plant ${plantName}`);

    // Timeout for enabling the water button
    setTimeout(
        function() {
            waterButton.disabled = false;
        },
        sleepTime * 1_000,
    );

    // Timeout for changing the progress bar
    let endTimeMilliseconds = Date.now() + sleepTime * 1_000;
    while(Date.now() < endTimeMilliseconds) {
        progressBar.value = waterButton.dataset.baseDisableTime - ((endTimeMilliseconds - Date.now()) / 1_000);
        await new Promise(r => setTimeout(r, 1_000));
    }
    progressBar.value = waterButton.dataset.baseDisableTime;
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

    // Disable the other buttons on the page
    for(let i of document.getElementsByClassName("water-button")) i.disabled = true;
    for(let i of document.getElementsByClassName("base-delete-button")) i.disabled = true;
    for(let i of document.getElementsByClassName("revive-button")) i.disabled = true;

    // Get the relevant information
    let plantName = object.getElementsByClassName("title")[0].textContent;

    // Perform our API request
    let jsonData = JSON.stringify({plant_name: plantName});
    console.log(`Sending data to /revive_plant: ${jsonData}`);
    let data = await fetch("/revive_plant", {
        method: "POST",
        body: jsonData,
        headers: {"Content-Type": "application/json"}
    })
    let response = await data.json()
    console.log(`Received response from /revive_plant: ${JSON.stringify(response)}`);
    return response.success;
}


async function changePlantColour(object) {
    let rangeObject = object;
    while(!object.classList.contains("plant")) object = object.parentNode;
    let plantImage = object.getElementsByClassName("plant-image")[0];
    plantImage.style.setProperty("filter", `hue-rotate(${rangeObject.value}deg)`);
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


async function buyPlant(object) {
    alert("This currently is non-functional.");
}
