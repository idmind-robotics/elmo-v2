
const SPEECH_URL = "api/onboard/speech";


/* SPEECH RECOGNITION */
// Check browser support for the SpeechRecognition API
if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
    // Create a new instance of the SpeechRecognition object
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
  
    // Set the language to Portuguese (Portugal)
    // recognition.lang = 'pt-PT';
    recognition.lang = 'en-US';
  
    // Event fired when speech recognition starts
    recognition.onstart = () => {
        console.log('Speech recognition started');
    };
  
    // Event fired when speech recognition results are available
    recognition.onresult = (event) => {
        console.log(JSON.stringify(event))
        const transcript = event.results[0][0].transcript;
        console.log('Recognized speech:', transcript);
        // update state
        fetch(SPEECH_URL, { 
            method: "POST",
            mode: "cors",
            cache: "no-cache",
            headers: {
                "Content-Type": "application/json" 
            },
            body: JSON.stringify({
                result: transcript
            })
        });
    };
  
    // Event fired when speech recognition ends
    recognition.onend = () => {
        console.log('Speech recognition ended');
        recognition.start();
    };
  
    // Event fired when an error occurs during speech recognition
    recognition.onerror = (event) => {
        console.log('Speech recognition error:', event.error);
    };

  recognition.start();

} else {
    console.log('Speech recognition not supported in this browser');
}
