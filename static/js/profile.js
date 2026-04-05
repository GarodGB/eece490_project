
$(document).ready(function() {
    loadProfile();
    loadMajors();
    
    $('#workloadRange').on('input', function() {
        const value = parseFloat($(this).val());
        $('#workloadValue').text(value.toFixed(1));
    });
});

function loadProfile() {
    API.get('/api/student/profile', function(response) {
        const profile = response.profile;
        
        $('#displayGPA').text(formatGPA(profile.gpa || 0));
        $('#displaySemester').text(profile.current_semester || 1);
        $('#displayUsername').text(profile.username || 'N/A');
        $('#displayEmail').text(profile.email || 'N/A');
        
        const majorCode = profile.major || 'N/A';
        if (majorCode !== 'N/A') {
            API.get('/api/majors', function(majorsResponse) {
                if (majorsResponse.success && majorsResponse.majors) {
                    const major = majorsResponse.majors.find(m => m.code === majorCode);
                    if (major && major.display) {
                        const displayName = major.display.split(' - ')[1] || major.name || majorCode;
                        $('#displayMajor').text(displayName);
                    } else {
                        $('#displayMajor').text(majorCode);
                    }
                } else {
                    $('#displayMajor').text(majorCode);
                }
            }, function() {
                $('#displayMajor').text(majorCode);
            });
        } else {
            $('#displayMajor').text('N/A');
        }
        
        if (profile.created_at) {
            const created = new Date(profile.created_at);
            $('#displayCreated').text(created.toLocaleDateString());
        }
        if (profile.updated_at) {
            const updated = new Date(profile.updated_at);
            $('#displayUpdated').text(updated.toLocaleDateString());
        }
        
        $('#strategySelect').val(profile.strategy || 'balanced');
        $('#workloadRange').val(profile.workload_tolerance || 0.5);
        $('#workloadValue').text(profile.workload_tolerance || 0.5);
        $('#currentSemesterInput').val(profile.current_semester || 1);
        
        if (profile.major) {
            $('#majorSelect').val(profile.major);
        }
    }, function(error) {
        console.error('Error loading profile:', error);
        showAlert('Failed to load profile. Please refresh the page.', 'danger');
    });
}

function loadMajors() {
    API.get('/api/majors', function(response) {
        if (response.success) {
            const select = $('#majorSelect');
            select.empty();
            response.majors.forEach(function(major) {
                select.append(`<option value="${major.code}">${major.display}</option>`);
            });
            
            loadProfile();
        }
    }, function(error) {
        console.error('Error loading majors:', error);
    });
}

function saveProfile() {
    const major = $('#majorSelect').val();
    const currentSemester = parseInt($('#currentSemesterInput').val());
    const strategy = $('#strategySelect').val();
    const workloadTolerance = parseFloat($('#workloadRange').val());
    
    if (!major) {
        showAlert('Please select a major', 'warning');
        return;
    }
    
    if (isNaN(currentSemester) || currentSemester < 1 || currentSemester > 20) {
        showAlert('Please enter a valid semester (1-20)', 'warning');
        return;
    }
    
    if (!strategy) {
        showAlert('Please select an academic strategy', 'warning');
        return;
    }
    
    if (isNaN(workloadTolerance) || workloadTolerance < 0 || workloadTolerance > 1) {
        showAlert('Please set a valid workload tolerance (0.0 - 1.0)', 'warning');
        return;
    }
    
    const data = {
        major: major,
        current_semester: currentSemester,
        strategy: strategy,
        workload_tolerance: workloadTolerance
    };
    
    const saveBtn = document.querySelector('#profileForm .btn-primary');
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
    
    API.post('/api/student/profile', data, function(response) {
        if (response && response.success) {
            showAlert('Profile updated successfully!', 'success');
            loadProfile();
        } else {
            const errorMsg = response && response.message ? response.message : 'Failed to update profile';
            showAlert(errorMsg, 'danger');
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalText;
        }
    }, function(error) {
        console.error('Error saving profile:', error);
        let errorMsg = 'Failed to update profile. Please try again.';
        if (error && error.responseJSON && error.responseJSON.message) {
            errorMsg = error.responseJSON.message;
        } else if (error && error.message) {
            errorMsg = error.message;
        }
        showAlert(errorMsg, 'danger');
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    });
    
    setTimeout(() => {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
    }, 2000);
}
