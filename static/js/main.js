
function initDarkMode() {
    var stored = localStorage.getItem('smart-academic-theme');
    var dark = stored === 'dark' || (!stored && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    if (dark) {
        document.body.classList.add('dark-mode');
    }
    var icon = document.getElementById('darkModeIcon');
    if (icon) {
        icon.classList.toggle('bi-moon-stars', !dark);
        icon.classList.toggle('bi-sun', dark);
    }
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDarkMode);
} else {
    initDarkMode();
}

function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    var isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('smart-academic-theme', isDark ? 'dark' : 'light');
    var icon = document.getElementById('darkModeIcon');
    if (icon) {
        icon.classList.toggle('bi-moon-stars', !isDark);
        icon.classList.toggle('bi-sun', isDark);
    }
}

function logout() {
    if (confirm('Are you sure you want to logout?')) {
        $.ajax({
            url: '/api/logout',
            method: 'POST',
            success: function() {
                window.location.href = '/';
            },
            error: function() {
                window.location.href = '/';
            }
        });
    }
}

function showAlert(message, type = 'info') {
    const alertDiv = $(`
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    $('main').prepend(alertDiv);
    setTimeout(() => alertDiv.fadeOut(), 5000);
}

function formatDifficulty(score) {
    if (score < 0.33) return { text: 'Easy', class: 'difficulty-easy' };
    if (score < 0.67) return { text: 'Medium', class: 'difficulty-medium' };
    return { text: 'Hard', class: 'difficulty-hard' };
}

function formatGPA(gpa) {
    return gpa.toFixed(2);
}

const API = {
    get: function(url, callback, errorCallback) {
        $.ajax({
            url: url,
            method: 'GET',
            success: function(response) {
                if (response.success !== false) {
                    callback(response);
                } else {
                    showAlert(response.message || 'Request failed', 'danger');
                    if (errorCallback) errorCallback(response);
                }
            },
            error: function(xhr, status, error) {
                console.error('API Error:', url, status, error);
                showAlert('Network error. Please try again.', 'danger');
                if (errorCallback) errorCallback({error: error, status: status});
            }
        });
    },
    
    post: function(url, data, callback, errorCallback) {
        return $.ajax({
            url: url,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function(response) {
                if (response.success !== false) {
                    callback(response);
                } else {
                    showAlert(response.message || 'Request failed', 'danger');
                    if (errorCallback) errorCallback(response);
                }
            },
            error: function(xhr, status, error) {
                console.error('API Error:', url, status, error);
                let errorData = {error: error, status: status};
                try {
                    if (xhr.responseJSON) {
                        errorData = {...errorData, ...xhr.responseJSON};
                    }
                } catch(e) {
                }
                if (errorCallback) {
                    errorCallback(errorData);
                } else {
                    showAlert('Network error. Please try again.', 'danger');
                }
            }
        });
    },
    
    put: function(url, data, callback, errorCallback) {
        return $.ajax({
            url: url,
            method: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function(response) {
                if (response.success !== false) {
                    callback(response);
                } else {
                    showAlert(response.message || 'Request failed', 'danger');
                    if (errorCallback) errorCallback(response);
                }
            },
            error: function(xhr, status, error) {
                console.error('API Error:', url, status, error);
                let errorData = {error: error, status: status};
                try {
                    if (xhr.responseJSON) {
                        errorData = {...errorData, ...xhr.responseJSON};
                    }
                } catch(e) {
                }
                if (errorCallback) {
                    errorCallback(errorData);
                } else {
                    showAlert('Network error. Please try again.', 'danger');
                }
            }
        });
    },
    
    delete: function(url, callback, errorCallback) {
        return $.ajax({
            url: url,
            method: 'DELETE',
            success: function(response) {
                if (response.success !== false) {
                    callback(response);
                } else {
                    showAlert(response.message || 'Request failed', 'danger');
                    if (errorCallback) errorCallback(response);
                }
            },
            error: function(xhr, status, error) {
                console.error('API Error:', url, status, error);
                let errorData = {error: error, status: status};
                try {
                    if (xhr.responseJSON) {
                        errorData = {...errorData, ...xhr.responseJSON};
                    }
                } catch(e) {
                }
                if (errorCallback) {
                    errorCallback(errorData);
                } else {
                    showAlert('Network error. Please try again.', 'danger');
                }
            }
        });
    }
};
