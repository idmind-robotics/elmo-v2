// const console_div = document.getElementById("div-console");
const img_eyes = document.getElementById("img-eyes");
const p_text = document.getElementById("p-text");
const video = document.getElementById("video");

const STATE_URL = "api/onboard";
const LOG_URL = "api/onboard/log";


function log(msg) {
    // console_div.innerHTML = msg;
}

log("Console ready.");


const ONBOARD_STATE = {
    "image": null,
    "text": null,
    "video": null,
    "url": null,
};


const reset_state = () => {
    ONBOARD_STATE.image = null;
    ONBOARD_STATE.text = null;
    ONBOARD_STATE.video = null;
    ONBOARD_STATE.url = null;
};


const show = (element) => {
    element.style.display = "block";
};


const show_flex = (element) => {
    element.style.display = "flex";
};


const hide = (element) => {
    element.style.display = "none";
};


hide(img_eyes);
hide(p_text);
hide(video);


const loadImage = (image_name) => {
    hide(video);
    hide(p_text);
    img_eyes.src = image_name;
    show(img_eyes);
};

const setText = (text) => {
    hide(img_eyes);
    hide(video);
    p_text.textContent = text.toUpperCase();
    show(p_text);
};



const playVideo = (video_name) => {
    hide(img_eyes);
    hide(p_text);
    hide(video);
    video.addEventListener("loadeddata", () => {
        loginfo("got video data")
        show(video);
    });
    video.src = video_name;
    video.setAttribute("crossorigin", "anonymous");
    video.play();
    // reset state after video ends
    video.addEventListener("ended", async () => {
        ONBOARD_STATE.video = null;
        // update state
        await fetch(STATE_URL, { 
            method: "POST",
            mode: "cors",
            cache: "no-cache",
            headers: {
                "Content-Type": "application/json" 
            },
            body: JSON.stringify(ONBOARD_STATE)
        });
    });
};


async function loop() {

    // get command
    const result = await fetch(STATE_URL);
    const data = await result.json();
    // process command
    if (data.image !== ONBOARD_STATE.image) {
        ONBOARD_STATE.image = data.image;
        if (data.image) {
            loginfo("loading image: " + data.image)
            loadImage(data.image);
        } else {
            hide(img_eyes);
        }
    }
    if (data.text !== ONBOARD_STATE.text) {
        ONBOARD_STATE.text = data.text;
        if (data.text) {
            loginfo("setting text: " + data.text)
            setText(data.text);
        } else {
            hide(p_text);
        }
    }
    if (data.video !== ONBOARD_STATE.video) {
        ONBOARD_STATE.video = data.video;
        if (data.video) {
            loginfo("playing video: " + data.video)
            playVideo(data.video);
        }
    }
    if (!ONBOARD_STATE.image && !ONBOARD_STATE.text && !ONBOARD_STATE.video) {
        ONBOARD_STATE.image = data.image;
        loadImage("images/normal.png");
    }
};


setInterval(loop, 100);

const loginfo = (msg) => {
    console.log(msg)

    return
    fetch(LOG_URL, { 
        method: "POST",
        mode: "cors",
        cache: "no-cache",
        headers: {
            "Content-Type": "application/json" 
        },
        body: JSON.stringify({
            info: msg
        })
    });
};

const logwarn = (msg) => {
    return
    fetch(LOG_URL, { 
        method: "POST",
        mode: "cors",
        cache: "no-cache",
        headers: {
            "Content-Type": "application/json" 
        },
        body: JSON.stringify({
            warn: msg
        })
    });
};

const logerror = (msg) => {
    return
    fetch(LOG_URL, { 
        method: "POST",
        mode: "cors",
        cache: "no-cache",
        headers: {
            "Content-Type": "application/json" 
        },
        body: JSON.stringify({
            error: msg
        })
    });
};
