document.addEventListener('DOMContentLoaded', function() {
    // Power button functionality
    const powerButton = document.querySelector('.power-button');
    const screen = document.querySelector('.screen');
    let isPoweredOn = true;

    powerButton.addEventListener('click', function() {
        isPoweredOn = !isPoweredOn;
        powerButton.classList.toggle('active');
        
        if (!isPoweredOn) {
            screen.classList.add('power-off');
            screen.classList.remove('power-on');
        } else {
            screen.classList.remove('power-off');
            screen.classList.add('power-on');
        }
    });

    // Knob controls functionality
    const knobs = document.querySelectorAll('.control-knob');
    const screenElement = document.querySelector('.screen'); // Cache screen element
    const chatContainer = document.querySelector('.chat-container'); // Cache chat container

    // Store current filter/style values
    let currentBrightness = parseFloat(localStorage.getItem('knob-BRIGHTNESS') || 0.5);
    let currentContrast = parseFloat(localStorage.getItem('knob-CONTRAST') || 0.5);
    let currentVHold = parseFloat(localStorage.getItem('knob-V-HOLD') || 0.5);

    // Apply initial saved values
    function applyInitialEffects() {
        // Map 0-1 value range to appropriate CSS values
        const brightnessValue = 0.7 + currentBrightness * 0.6; // Range 0.7 to 1.3
        const contrastValue = 0.7 + currentContrast * 0.8; // Range 0.7 to 1.5
        const vHoldOffset = (currentVHold - 0.5) * 10; // Range -5px to 5px

        screenElement.style.filter = `brightness(${brightnessValue}) contrast(${contrastValue})`;
        if (chatContainer) {
            chatContainer.style.setProperty('--v-hold-offset', `${vHoldOffset}px`);
        }
    }

    knobs.forEach(knob => {
        let currentRotation = 0;
        let isDragging = false;
        let startY = 0;
        let lastAppliedValue = 0.5; // Use stored value below

        // Initialize knob rotation from stored value
        const labelElement = knob.parentElement.querySelector('.control-label');
        const knobType = labelElement ? labelElement.textContent : 'UNKNOWN';
        let storedValue;
        switch(knobType) {
            case 'BRIGHTNESS': storedValue = currentBrightness; break;
            case 'CONTRAST': storedValue = currentContrast; break;
            case 'V-HOLD': storedValue = currentVHold; break;
            default: storedValue = 0.5;
        }
        lastAppliedValue = parseFloat(storedValue);
        currentRotation = lastAppliedValue * 300 - 150; // Convert 0-1 value to -150 to 150 degrees
        knob.style.transform = `rotate(${currentRotation}deg)`;

        function applyKnobEffect(type, value) {
            // Update the stored current value for the specific knob
            switch(type) {
                case 'BRIGHTNESS':
                    currentBrightness = value;
                    localStorage.setItem(`knob-BRIGHTNESS`, value);
                    break;
                case 'CONTRAST':
                    currentContrast = value;
                    localStorage.setItem(`knob-CONTRAST`, value);
                    break;
                case 'V-HOLD':
                    currentVHold = value;
                    localStorage.setItem(`knob-V-HOLD`, value);
                    break;
            }

            // Apply all effects based on current values
            applyInitialEffects(); // Re-use the function to apply combined effects
        }

        knob.addEventListener('mousedown', function(e) {
            isDragging = true;
            startY = e.clientY;
            knob.style.cursor = 'grabbing';
            document.body.style.cursor = 'grabbing';
            e.preventDefault(); // Prevent text selection
        });

        document.addEventListener('mousemove', function(e) {
            if (!isDragging) return;

            // Calculate vertical movement
            const deltaY = startY - e.clientY;
            const sensitivity = 0.5; // Adjust this value to change rotation speed
            
            // Update rotation based on vertical movement
            currentRotation = Math.max(-150, Math.min(150, currentRotation + deltaY * sensitivity));
            knob.style.transform = `rotate(${currentRotation}deg)`;
            
            // Calculate value (0 to 1)
            const value = (currentRotation + 150) / 300;
            
            // Only apply if value has changed significantly
            if (Math.abs(value - lastAppliedValue) > 0.01) {
                const knobTypeLabel = knob.parentElement.querySelector('.control-label');
                if (knobTypeLabel) {
                    applyKnobEffect(knobTypeLabel.textContent, value);
                    lastAppliedValue = value;
                }
            }
            
            startY = e.clientY;
        });

        document.addEventListener('mouseup', function() {
            if (isDragging) {
                isDragging = false;
                knob.style.cursor = 'grab';
                document.body.style.cursor = 'default';
            }
        });

        // Add hover effect
        knob.addEventListener('mouseover', function() {
            knob.style.cursor = isDragging ? 'grabbing' : 'grab';
        });

        // Add keyboard controls
        knob.addEventListener('keydown', function(e) {
            const step = e.shiftKey ? 15 : 5;
            let newRotation = currentRotation;

            if (e.key === 'ArrowUp') {
                newRotation = Math.min(150, currentRotation + step);
            } else if (e.key === 'ArrowDown') {
                newRotation = Math.max(-150, currentRotation - step);
            }

            if (newRotation !== currentRotation) {
                currentRotation = newRotation;
                knob.style.transform = `rotate(${currentRotation}deg)`;
                const value = (currentRotation + 150) / 300;
                const knobTypeLabel = knob.parentElement.querySelector('.control-label');
                if (knobTypeLabel) {
                    applyKnobEffect(knobTypeLabel.textContent, value);
                }
            }
        });

        // Make knobs focusable
        knob.setAttribute('tabindex', '0');
    });

    // Apply initial effects on load
    applyInitialEffects();
}); 