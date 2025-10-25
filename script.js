document.addEventListener("DOMContentLoaded", () => {
    const messagesDiv = document.getElementById("chat-messages");
    const input = document.getElementById("message-input");
    const sendButton = document.getElementById("send-button");
    const reportButton = document.getElementById("report-button");
    const pdfButton = document.getElementById("pdf-button");
    const micButton = document.getElementById("mic-button");
    
    // Voice-to-Text Setup
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let isListening = false;

    // Read Aloud Setup
    const synth = window.speechSynthesis;
    const { jsPDF } = window.jspdf;
    let currentReportText = "";

    // Inside script.js:
    const speakText = (text) => {
        if (synth.speaking) {
            synth.cancel(); 
        }
        const utterance = new SpeechSynthesisUtterance(text);
        
        utterance.rate = 0.9; 
        
        // --- THIS IS THE FIX ---
        // Replace 'Samantha' with the name you found in the console (e.g., 'Kate', 'Serena')
        const femaleVoice = synth.getVoices().find(voice => voice.name.includes('Samantha')); 
        if (femaleVoice) {
            utterance.voice = femaleVoice;
        }
        // --- END FIX ---
        
        synth.speak(utterance);
    };

    let chatHistory = [{
        role: "assistant",
        content: "Hi, I'm your AI Nurse assistant. I'm here to gather some information about your symptoms. To start, please type 'Hi' or 'Hello'."
    }];

    // --- Speech Recognition Logic ---
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.lang = 'en-US';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onresult = (event) => {
            const transcript = event.results[event.results.length - 1][0].transcript.trim();
            input.value = transcript;
            stopListening();
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);
            addMessage("assistant", `Sorry, I couldn't understand that. Error: ${event.error}`);
            stopListening();
        };

        recognition.onend = () => {
             if (isListening) {
                stopListening();
             }
        };

    } else {
        micButton.style.display = 'none';
        console.warn("Speech Recognition not supported by this browser.");
    }

    const startListening = () => {
        if (!recognition || isListening) return;
        try {
            recognition.start();
            isListening = true;
            micButton.classList.add("listening");
            micButton.textContent = "Listening...";
            input.placeholder = "Speak now...";
        } catch (err) {
            console.error("Error starting recognition:", err);
            addMessage("assistant", "Could not start voice recognition. Please check microphone permissions.");
            stopListening();
        }
    };

    const stopListening = () => {
        if (!recognition || !isListening) return;
        recognition.stop();
        isListening = false;
        micButton.classList.remove("listening");
        micButton.textContent = "Tap to Speak";
        input.placeholder = "Type or click mic...";
    };

    micButton.addEventListener('click', () => {
        if (isListening) {
            stopListening();
        } else {
            startListening();
        }
    });
    // --- End Speech Recognition Logic ---

    const addMessage = (role, content) => {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message", role);

        let textToSpeak = content;

        if (role === 'report') {
            currentReportText = content;
            pdfButton.style.display = "block";

            messageDiv.classList.add('assistant');
            let htmlContent = '<h2>Clinical Prep Report</h2>';
            const lines = content.split('\n');
            let inList = false;
            
            lines.forEach(line => {
                if (!line.trim()) { 
                    inList = false;
                    htmlContent += '<br>';
                    return;
                }
                if (line.startsWith('**') && line.endsWith('**')) {
                    inList = false;
                    htmlContent += `<h3>${line.substring(2, line.length - 2)}</h3>`;
                } else if (line.match(/^\s*\d+\.\s/)) { 
                    inList = false;
                    htmlContent += `<h4>${line.trim()}</h4>`;
                } else if (line.trim().startsWith('-')) {
                    if (!inList) {
                        htmlContent += '<ul>';
                        inList = true;
                    }
                    htmlContent += `<li>${line.substring(line.indexOf('-') + 1).trim()}</li>`;
                } else {
                    if (inList) {
                        htmlContent += '</ul>';
                        inList = false;
                    }
                    htmlContent += `<p>${line}</p>`;
                }
            });
            if (inList) htmlContent += '</ul>';
            messageDiv.innerHTML = htmlContent;

            textToSpeak = content.replace(/\*\*/g, ''); 

        } else {
            messageDiv.textContent = content;
        }

        // Add the speaker button to all messages
        const speakerButton = document.createElement('button');
        speakerButton.className = 'read-aloud-button';
        speakerButton.textContent = '🔊'; 
        speakerButton.onclick = () => speakText(textToSpeak);

        messageDiv.appendChild(speakerButton);

        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    };

    const sendMessage = async () => {
        const messageText = input.value.trim();
        if (!messageText) return;

        if (isListening) {
            stopListening();
        }

        addMessage("user", messageText);
        chatHistory.push({ role: "user", content: messageText });
        input.value = "";
        pdfButton.style.display = "none";
        currentReportText = "";

        const response = await fetch("http://127.0.0.1:8000/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ messages: chatHistory })
        });

        const data = await response.json();
        addMessage("assistant", data.response);
        chatHistory.push({ role: "assistant", content: data.response });
    };

    const generateReport = async () => {
        if (isListening) {
            stopListening();
        }
        addMessage("assistant", "Understood. I will now generate the clinical prep report based on our conversation...");

        const response = await fetch("http://127.0.0.1:8000/generate_report", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ messages: chatHistory })
        });

        const data = await response.json();
        addMessage("report", data.report);
    };

    const downloadPDF = () => {
        if (!currentReportText) return;
        const doc = new jsPDF();
        const margin = 10;
        let y = margin;
        const lines = doc.splitTextToSize(currentReportText, 180);
        lines.forEach(line => { 
            let isBold = false;
            if (line.startsWith('**') && line.endsWith('**')) {
                doc.setFont(undefined, 'bold');
                line = line.substring(2, line.length - 2);
                isBold = true;
            }
            doc.text(line, margin, y);
            y += 7;
            if (isBold) {
                doc.setFont(undefined, 'normal');
            }
            if (y > 280) {
                doc.addPage();
                y = margin;
            }
        });
        doc.save("Clinical-Prep-Report.pdf");
    };

    pdfButton.addEventListener("click", downloadPDF);
    sendButton.addEventListener("click", sendMessage);
    input.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !e.shiftKey) { 
            e.preventDefault(); 
            sendMessage();
        }
    });
    reportButton.addEventListener("click", generateReport);
});