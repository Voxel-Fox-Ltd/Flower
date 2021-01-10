async function water_plant(object) {
    object = object.parentNode.parentNode.parentNode;

    // Get the relevant information
    let plantName = object.getElementsByClassName("title")[0].textContent;
    let progressBar = object.getElementsByClassName("progress")[0];
    let nourishmentNode = object.getElementsByClassName("nourishment")[0];

    // Set up the progress bar
    let currentProgressBarValue = progressBar.getAttribute("value");
    progressBar.setAttribute("value", "");

    // Perform our API request
    let jsonData = JSON.stringify({plant_name: plantName});
    console.log(`Sending data ${jsonData}`);
    let data = await fetch("/water_plant", {
        method: "POST",
        body: jsonData,
        headers: {"Content-Type": "application/json"}
    })
    let response = await data.json()
    console.log(`Received response ${JSON.stringify(response)}`);

    // See if it was correct
    if (response.success) {
        console.log("Changing to new attrbites");
        progressBar.setAttribute("value", response.new_nourishment_level / 21);
        nourishmentNode.innerHTML = response.new_nourishment_level;
        console.log("Changed");
    }
    else {
        progressBar.setAttribute("value", currentProgressBarValue);
    }

}
