// DeepSeek Functions Module
class DeepSeekManager {
    constructor() {
        this.activeTriggerTests = [];
        this.travelConversationId = null;
        this.currentTravelStep = null;
    }

    // DeepSeek Settings Functions
    async loadDeepSeekSettings() {
        try {
            const response = await fetch('/api/v1/admin/settings?category=deepseek');
            const data = await response.json();
            
            if (data.status === 'success' && data.data.settings) {
                const settings = data.data.settings;
                
                // Populate form fields
                this.setFieldValue('deepseek-api-key', settings.api_key || '');
                this.setFieldValue('deepseek-model', settings.model || 'deepseek-chat');
                this.setFieldValue('deepseek-max-tokens', settings.max_tokens || 4096);
                this.setFieldValue('deepseek-temperature', settings.temperature || 0.7);
                this.setFieldValue('deepseek-requests-per-minute', settings.requests_per_minute || 50);
                this.setFieldValue('deepseek-tokens-per-minute', settings.tokens_per_minute || 100000);
                this.setFieldValue('deepseek-timeout', settings.timeout || 60);
                this.setFieldValue('deepseek-max-retries', settings.max_retries || 3);
                this.setFieldValue('deepseek-travel-memory', settings.travel_memory || '');
                
                // Update status
                this.updateStatusDisplay(settings);
                
                console.log('DeepSeek settings loaded successfully');
            }
        } catch (error) {
            console.error('Error loading DeepSeek settings:', error);
            this.showAlert('Error loading DeepSeek settings: ' + error.message, 'danger');
        }
    }

    async saveDeepSeekSettings() {
        try {
            const settingsData = {
                category: 'deepseek',
                settings: {
                    api_key: this.getFieldValue('deepseek-api-key'),
                    model: this.getFieldValue('deepseek-model'),
                    max_tokens: parseInt(this.getFieldValue('deepseek-max-tokens')),
                    temperature: parseFloat(this.getFieldValue('deepseek-temperature')),
                    requests_per_minute: parseInt(this.getFieldValue('deepseek-requests-per-minute')),
                    tokens_per_minute: parseInt(this.getFieldValue('deepseek-tokens-per-minute')),
                    timeout: parseInt(this.getFieldValue('deepseek-timeout')),
                    max_retries: parseInt(this.getFieldValue('deepseek-max-retries')),
                    travel_memory: this.getFieldValue('deepseek-travel-memory')
                }
            };

            const response = await fetch('/api/v1/admin/settings', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(settingsData)
            });

            const result = await response.json();
            
            if (result.status === 'success') {
                this.showAlert('DeepSeek settings saved successfully!', 'success');
                this.loadDeepSeekSettings(); // Reload to show updated values
            } else {
                this.showAlert('Error saving settings: ' + (result.detail || 'Unknown error'), 'danger');
            }
        } catch (error) {
            console.error('Error saving DeepSeek settings:', error);
            this.showAlert('Error saving DeepSeek settings: ' + error.message, 'danger');
        }
    }

    async testDeepSeekConnection() {
        try {
            this.updateElement('deepseek-api-status', 'Testing...');
            
            const response = await fetch('/api/v1/deepseek/test-connection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    api_key: this.getFieldValue('deepseek-api-key'),
                    model: this.getFieldValue('deepseek-model')
                })
            });

            const result = await response.json();
            
            if (result.status === 'success') {
                this.updateElement('deepseek-api-status', 'Connected ✓');
                this.setElementClass('deepseek-api-status', 'text-success');
                this.showAlert('DeepSeek connection successful!', 'success');
            } else {
                this.updateElement('deepseek-api-status', 'Failed ✗');
                this.setElementClass('deepseek-api-status', 'text-danger');
                this.showAlert('Connection failed: ' + (result.detail || 'Unknown error'), 'danger');
            }
        } catch (error) {
            console.error('Error testing DeepSeek connection:', error);
            this.updateElement('deepseek-api-status', 'Error ✗');
            this.setElementClass('deepseek-api-status', 'text-danger');
            this.showAlert('Error testing connection: ' + error.message, 'danger');
        }
    }

    // Trigger Demo Functions
    testTimeTrigger(seconds) {
        const testId = Date.now();
        const triggerTest = {
            id: testId,
            type: 'time_based',
            description: `${seconds}s After Check-in`,
            startTime: Date.now(),
            duration: seconds * 1000
        };
        
        this.activeTriggerTests.push(triggerTest);
        this.updateActiveTriggers();
        
        this.addTriggerResult(`⏰ Time-based trigger started: ${seconds} seconds`, 'info');
        
        setTimeout(() => {
            this.addTriggerResult(`✅ Time trigger fired: Welcome message sent!`, 'success');
            this.removeTriggerTest(testId);
        }, seconds * 1000);
    }

    testEventTrigger(eventType) {
        this.addTriggerResult(`📨 Event trigger: ${eventType} - Processing...`, 'info');
        
        setTimeout(() => {
            this.addTriggerResult(`✅ Event trigger fired: Auto-response sent!`, 'success');
        }, 1000);
    }

    testSentimentTrigger() {
        this.addTriggerResult(`😔 Sentiment trigger: Negative sentiment detected`, 'warning');
        
        setTimeout(() => {
            this.addTriggerResult(`🚨 Staff notification sent! Manager will contact guest.`, 'danger');
        }, 2000);
    }

    testFirstMessageTrigger(seconds) {
        const testId = Date.now();
        const triggerTest = {
            id: testId,
            type: 'first_message',
            description: `${seconds}s After First Message`,
            startTime: Date.now(),
            duration: seconds * 1000
        };
        
        this.activeTriggerTests.push(triggerTest);
        this.updateActiveTriggers();
        
        this.addTriggerResult(`💬 First message trigger started: ${seconds} seconds`, 'info');
        
        setTimeout(() => {
            this.addTriggerResult(`✅ Follow-up message sent: "How was your first day?"`, 'success');
            this.removeTriggerTest(testId);
        }, seconds * 1000);
    }

    testVIPTrigger() {
        this.addTriggerResult(`👑 VIP condition trigger: Checking guest status...`, 'info');
        
        setTimeout(() => {
            this.addTriggerResult(`✨ VIP trigger fired: Special welcome message with champagne offer!`, 'success');
        }, 1500);
    }

    clearTriggerTests() {
        this.activeTriggerTests = [];
        this.updateActiveTriggers();
        const resultsDiv = document.getElementById('trigger-test-results');
        if (resultsDiv) {
            resultsDiv.innerHTML = '';
        }
    }

    addTriggerResult(message, type) {
        const resultsDiv = document.getElementById('trigger-test-results');
        if (!resultsDiv) return;
        
        const alertClass = type === 'success' ? 'alert-success' : 
                         type === 'warning' ? 'alert-warning' :
                         type === 'danger' ? 'alert-danger' : 'alert-info';
        
        const resultHtml = `
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        resultsDiv.insertAdjacentHTML('afterbegin', resultHtml);
    }

    updateActiveTriggers() {
        const activeDiv = document.getElementById('active-triggers');
        if (!activeDiv) return;
        
        if (this.activeTriggerTests.length === 0) {
            activeDiv.innerHTML = '<div class="text-muted">No active tests</div>';
            return;
        }
        
        const html = this.activeTriggerTests.map(test => {
            const elapsed = Math.floor((Date.now() - test.startTime) / 1000);
            const remaining = Math.max(0, Math.floor(test.duration / 1000) - elapsed);
            
            return `
                <div class="active-trigger-item">
                    <small>${test.description}</small>
                    <span class="badge bg-primary trigger-countdown">${remaining}s</span>
                </div>
            `;
        }).join('');
        
        activeDiv.innerHTML = html;
    }

    removeTriggerTest(testId) {
        this.activeTriggerTests = this.activeTriggerTests.filter(test => test.id !== testId);
        this.updateActiveTriggers();
    }

    // Travel Demo Functions
    async startTravelDemo() {
        const phoneNumber = this.getFieldValue('travel-guest-phone');
        if (!phoneNumber) {
            this.showAlert('Please enter a phone number', 'warning');
            return;
        }
        
        // Detect language from phone number
        const language = this.detectLanguageFromPhone(phoneNumber);
        this.updateElement('detected-language', language.toUpperCase());
        
        // Show conversation area
        this.showElement('travel-conversation-demo');
        
        // Start conversation
        const greeting = "Здравствуйте! Я могу улучшить ваш отпуск на 50% больше эмоций и впечатлений бесплатно. У меня есть лучшие варианты как провести время. Хотите узнать?";
        
        this.addTravelMessage('bot', greeting);
        this.currentTravelStep = 'greeting';
        
        // Update language detection info
        this.updateElement('language-detection-info', `
            <div class="mb-2">
                <strong>Phone:</strong> ${phoneNumber}<br>
                <strong>Detected:</strong> ${language.toUpperCase()}<br>
                <strong>Confidence:</strong> 85%
            </div>
        `);
    }

    detectLanguageFromPhone(phone) {
        if (phone.startsWith('+7') || phone.startsWith('7')) return 'ru';
        if (phone.startsWith('+66') || phone.startsWith('66')) return 'th';
        if (phone.startsWith('+86') || phone.startsWith('86')) return 'zh';
        if (phone.startsWith('+1') || phone.startsWith('1')) return 'en';
        return 'en'; // default
    }

    sendTravelMessage() {
        const input = document.getElementById('travel-user-input');
        if (!input) return;
        
        const message = input.value.trim();
        if (!message) return;
        
        this.addTravelMessage('user', message);
        input.value = '';
        
        // Process response based on current step
        setTimeout(() => {
            this.processTravelResponse(message);
        }, 1000);
    }

    processTravelResponse(userMessage) {
        let botResponse = '';
        
        switch (this.currentTravelStep) {
            case 'greeting':
                if (userMessage.toLowerCase().includes('да') || userMessage.toLowerCase().includes('yes')) {
                    botResponse = 'Отлично! Скажите, какой раз вы на Пхукете?\n\n1. Первый раз\n2. 2-3 раза\n3. Более 3 раз';
                    this.currentTravelStep = 'visit_frequency';
                } else {
                    botResponse = 'Понимаю! Если передумаете, просто напишите мне. Хорошего отдыха!';
                    this.currentTravelStep = 'ended';
                }
                break;
                
            case 'visit_frequency':
                botResponse = 'Понятно! А с кем вы приехали?\n\n1. Один/одна\n2. С партнером\n3. С детьми\n4. Компанией друзей';
                this.currentTravelStep = 'companions';
                break;
                
            case 'companions':
                botResponse = 'Замечательно! Основываясь на ваших ответах, вот мои персональные рекомендации:\n\n🏖️ Пляж Ката - идеален для пар\n🌅 Смотровая Промтеп - лучшие закаты\n🍽️ Ресторан Mom Tri\'s - романтичные ужины\n🏛️ Старый город - красивые фото\n\nХотите больше деталей по любой из рекомендаций?';
                this.currentTravelStep = 'recommendations';
                break;
                
            default:
                botResponse = 'Спасибо за интерес! Наслаждайтесь отдыхом на Пхукете! 🌴';
        }
        
        this.addTravelMessage('bot', botResponse);
    }

    addTravelMessage(sender, message) {
        const messagesDiv = document.getElementById('travel-messages');
        if (!messagesDiv) return;
        
        const isBot = sender === 'bot';
        
        const messageHtml = `
            <div class="travel-message ${sender}">
                <div class="d-flex align-items-center mb-1">
                    <i class="fas fa-${isBot ? 'robot' : 'user'} me-2"></i>
                    <small class="text-muted">${isBot ? 'Travel Assistant' : 'Guest'}</small>
                </div>
                <div style="white-space: pre-line;">${message}</div>
            </div>
        `;
        
        messagesDiv.insertAdjacentHTML('beforeend', messageHtml);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    // Utility functions
    getFieldValue(id) {
        const element = document.getElementById(id);
        return element ? element.value : '';
    }

    setFieldValue(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.value = value;
        }
    }

    updateElement(id, content) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = content;
        }
    }

    setElementClass(id, className) {
        const element = document.getElementById(id);
        if (element) {
            element.className = className;
        }
    }

    showElement(id) {
        const element = document.getElementById(id);
        if (element) {
            element.style.display = 'block';
        }
    }

    hideElement(id) {
        const element = document.getElementById(id);
        if (element) {
            element.style.display = 'none';
        }
    }

    showAlert(message, type) {
        // Create and show bootstrap alert
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Add to page (you might want to specify a container)
        document.body.insertBefore(alertDiv, document.body.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 5000);
    }

    updateStatusDisplay(settings) {
        this.updateElement('deepseek-current-model', settings.model || 'deepseek-chat');
        this.updateElement('deepseek-memory-size', 
            Math.round((settings.travel_memory || '').length / 1024) + ' KB');
    }

    // Initialize periodic updates
    startPeriodicUpdates() {
        // Update active triggers every second
        setInterval(() => {
            this.updateActiveTriggers();
        }, 1000);
    }
}

// Global instance
const deepSeekManager = new DeepSeekManager();

// Global functions for backward compatibility
function loadDeepSeekSettings() {
    return deepSeekManager.loadDeepSeekSettings();
}

function saveDeepSeekSettings() {
    return deepSeekManager.saveDeepSeekSettings();
}

function testDeepSeekConnection() {
    return deepSeekManager.testDeepSeekConnection();
}

function testTimeTrigger(seconds) {
    return deepSeekManager.testTimeTrigger(seconds);
}

function testEventTrigger(eventType) {
    return deepSeekManager.testEventTrigger(eventType);
}

function testSentimentTrigger() {
    return deepSeekManager.testSentimentTrigger();
}

function testFirstMessageTrigger(seconds) {
    return deepSeekManager.testFirstMessageTrigger(seconds);
}

function testVIPTrigger() {
    return deepSeekManager.testVIPTrigger();
}

function clearTriggerTests() {
    return deepSeekManager.clearTriggerTests();
}

function startTravelDemo() {
    return deepSeekManager.startTravelDemo();
}

function sendTravelMessage() {
    return deepSeekManager.sendTravelMessage();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    deepSeekManager.startPeriodicUpdates();
});
