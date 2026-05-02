
let selectedCourses = [];
let searchTimeout;
let currentRecommendations = [];

$(document).ready(function() {
    loadProfile();
    setTimeout(function() {
        loadRecommendations();
    }, 500);
    loadCompletedCourses();
    loadUnlockedCourses();
    loadAvailableCourses();
    loadAcademicJourneySection();
    if ($('#performance').hasClass('active')) {
        loadPerformanceDashboard();
    }
    if ($('#aiInsights').hasClass('active')) {
        loadAIInsights();
    }
    
    $('#courseSearch').on('input', function() {
        clearTimeout(searchTimeout);
        const query = $(this).val();
        if (query.length >= 2) {
            searchTimeout = setTimeout(() => searchCourses(query), 500);
        }
    });
    
    $('#chatInput').on('keypress', function(e) {
        if (e.which === 13) {
            sendChatMessage();
        }
    });
    
    $('.modal').on('keypress', 'input, textarea, select', function(e) {
        if (e.which === 13) {
            e.preventDefault();
            const modal = $(this).closest('.modal');
            const saveBtn = modal.find('button[onclick*="save"], button[onclick*="add"], button[onclick*="create"]').first();
            if (saveBtn.length && !saveBtn.prop('disabled')) {
                saveBtn.click();
            }
        }
    });
    
    $('.modal form').on('submit', function(e) {
        e.preventDefault();
        const modal = $(this).closest('.modal');
        const saveBtn = modal.find('button[onclick*="save"], button[onclick*="add"], button[onclick*="create"]').first();
        if (saveBtn.length && !saveBtn.prop('disabled')) {
            saveBtn.click();
        }
    });
    
    $('#workloadRange').on('input', function() {
        const value = parseFloat($(this).val());
        $('#workloadValue').text(value.toFixed(1));
    });
    
    $('.modal').on('show.bs.modal', function() {
        $(this).attr('aria-hidden', 'false');
        $(this).find('button[onclick*="save"], button[onclick*="add"], button[onclick*="create"]').prop('disabled', false);
    });
    
    $('.modal').on('hidden.bs.modal', function() {
        $(this).attr('aria-hidden', 'true');
        $(this).find('button[onclick*="save"], button[onclick*="add"], button[onclick*="create"]').prop('disabled', false);
    });

    $('button[data-bs-target="#prereqGraph"]').on('shown.bs.tab', function() {
        loadPrereqGraph();
    });

    $('button[data-bs-target="#bottlenecks"]').on('shown.bs.tab', function() {
        loadBottlenecks();
    });
    
    $('button[data-bs-target="#performance"]').on('shown.bs.tab', function() {
        loadPerformanceDashboard();
    });

    $('button[data-bs-target="#recommendations"]').on('shown.bs.tab', function() {
        loadRecommendationGoalsFromProfile();
    });

    $('#recWorkloadRange').on('input', function() {
        const value = parseFloat($(this).val());
        $('#recWorkloadValue').text(value.toFixed(1));
    });
});

let prereqGraphNetwork = null;

/** Major vs gen-ed electives vs math/science support (matches server catalog_bucket). */
function catalogBucket(course) {
    if (!course) return 'elective';

    const type = String(course.course_type || '').trim().toLowerCase();
    const bucket = String(course.catalog_bucket || '').trim().toLowerCase();
    const tag = String(course.catalog_tag || '').trim().toLowerCase();
    const subject = String(course.subject || '').trim().toUpperCase();
    const name = String(course.name || '').trim().toLowerCase();
    const code = String(course.course_code || '').trim().toUpperCase();

    // Manual correction: courses named "ECE Elective..." should appear as Elective,
    // even if the old backend still marks them as major/core.
    if (
        name.includes('elective') ||
        code.includes('ELECTIVE') ||
        type === 'major_elective' ||
        type === 'general_elective' ||
        bucket === 'elective' ||
        tag === 'elective'
    ) {
        return 'elective';
    }

    if (
        type === 'support' ||
        bucket === 'support' ||
        tag === 'support' ||
        ['MATH', 'PHYS', 'CHEM', 'STAT', 'ENGL', 'ENG'].includes(subject)
    ) {
        return 'support';
    }

    if (type === 'core' || bucket === 'major' || tag === 'major') {
        return 'major';
    }

    return 'elective';
}

function catalogRoleItemClass(course) {
    const k = catalogBucket(course);
    if (k === 'elective') return 'course-item--elective';
    if (k === 'support') return 'course-item--support';
    return 'course-item--major';
}

function formatCatalogRoleBadge(course) {
    const k = catalogBucket(course);
    if (k === 'elective') {
        return '<span class="role-badge role-badge--elective"><i class="bi bi-stars" aria-hidden="true"></i> Elective</span>';
    }
    if (k === 'support') {
        return '<span class="role-badge role-badge--support"><i class="bi bi-calculator" aria-hidden="true"></i> Support</span>';
    }
    return '<span class="role-badge role-badge--major"><i class="bi bi-mortarboard-fill" aria-hidden="true"></i> Major</span>';
}
function catalogRoleItemClass(course) {
    const k = catalogBucket(course);
    if (k === 'elective') return 'course-item--elective';
    if (k === 'support') return 'course-item--support';
    return 'course-item--major';
}

function formatCatalogRoleBadge(course) {
    const k = catalogBucket(course);
    if (k === 'elective') {
        return '<span class="role-badge role-badge--elective"><i class="bi bi-stars" aria-hidden="true"></i> Elective</span>';
    }
    if (k === 'support') {
        return '<span class="role-badge role-badge--support"><i class="bi bi-calculator" aria-hidden="true"></i> Support</span>';
    }
    return '<span class="role-badge role-badge--major"><i class="bi bi-mortarboard-fill" aria-hidden="true"></i> Major</span>';
}

function labBadgeHtml(course) {
    if (!course || !course.is_lab) return '';
    return '<span class="badge badge-rec-lab rounded-pill ms-1"><i class="bi bi-flask" aria-hidden="true"></i> Lab</span>';
}

function loadPrereqGraph() {
    const container = document.getElementById('prereqGraphContainer');
    if (!container) return;
    container.innerHTML = '<div class="d-flex align-items-center justify-content-center h-100"><div class="spinner-border text-primary" role="status"></div><span class="ms-2">Loading graph...</span></div>';
    const planCodes = getPlanCourseCodes();
    const q = planCodes.length
        ? ('?plan_codes=' + encodeURIComponent(planCodes.join(',')))
        : '';
    API.get('/api/prerequisite-graph' + q, function(response) {
        if (!response.success || !response.graph) {
            container.innerHTML = '<p class="text-muted text-center py-5">No graph data available.</p>';
            return;
        }
        const g = response.graph;
        const nodes = new vis.DataSet((g.nodes || []).map(function(n) {
            let color = '#6b7280';
            if (n.status === 'completed') color = '#059669';
            else if (n.status === 'unlocked') color = '#3b82f6';
            return { id: n.id, label: n.label, title: n.title || n.label, color: color };
        }));
        const edges = new vis.DataSet((g.edges || []).map(function(e) { return { from: e.from, to: e.to }; }));
        const data = { nodes: nodes, edges: edges };
        const options = {
            nodes: { shape: 'box', font: { size: 12 } },
            edges: { arrows: 'to' },
            layout: { hierarchical: { direction: 'UD', sortMethod: 'directed' } },
            physics: false
        };
        if (prereqGraphNetwork) prereqGraphNetwork.destroy();
        prereqGraphNetwork = new vis.Network(container, data, options);
    }, function() {
        container.innerHTML = '<p class="text-danger text-center py-5">Failed to load graph. Try again.</p>';
    });
}

function getPlanCourseCodes() {
    if (selectedCourses && selectedCourses.length > 0) return selectedCourses.map(c => c.code).filter(Boolean);
    if (currentRecommendations && currentRecommendations.length > 0) return currentRecommendations.map(c => c.course_code).filter(Boolean);
    // Fallback: read codes directly from the rendered planner table (handles the
    // ML hybrid recommender path which doesn't populate the globals above).
    const rows = document.querySelectorAll('#plannerTableBody tr');
    const codes = [];
    rows.forEach(function(row) {
        const cell = row.cells && row.cells[0];
        if (!cell) return;
        const text = (cell.textContent || '').trim().toUpperCase();
        // Skip empty-state rows like "No recommendations found..."
        if (text && /^[A-Z]{2,5}\s*\d{2,4}[A-Z]?$/i.test(text.replace(/\s+/g, ''))) {
            codes.push(text.replace(/\s+/g, ''));
        }
    });
    return codes;
}

function runWhatIfGpa() {
    const targetGpa = parseFloat($('#whatIfTargetGpa').val()) || 3.0;
    const courseCodes = getPlanCourseCodes();
    API.post('/api/gpa/what-if', { target_gpa: targetGpa, course_codes: courseCodes }, function(res) {
        if (!res.success) { $('#whatIfGpaResult').html('<span class="text-danger">' + (res.message || 'Error') + '</span>'); return; }
        let msg = 'Current GPA: ' + res.current_gpa + ' (' + res.current_credits + ' credits). ';
        if (res.semester_credits > 0 && res.required_gpa_this_semester != null) {
            msg += res.achievable ? 'To reach ' + res.target_gpa + ', you need <strong>' + res.required_gpa_this_semester + '</strong> this semester (' + res.semester_credits + ' credits).' : res.message;
        } else {
            msg += res.message || 'Add courses to your plan to see required GPA.';
        }
        $('#whatIfGpaResult').html(msg);
    }, function() { $('#whatIfGpaResult').html('<span class="text-danger">Request failed.</span>'); });
}

function runGpaSimulate() {
    const courses = [];
    $('.simulate-grade').each(function() {
        const code = $(this).data('code');
        const grade = $(this).val();
        if (code && grade) courses.push({ course_code: code, grade: grade });
    });
    if (courses.length === 0) {
        $('#simulateGpaResult').text('Add courses and grades first.').addClass('text-muted').removeClass('text-success');
        return;
    }
    API.post('/api/gpa/simulate', { courses: courses }, function(res) {
        if (res.success) $('#simulateGpaResult').text('Simulated GPA: ' + res.simulated_gpa).removeClass('text-muted').addClass('text-success fw-bold');
        else $('#simulateGpaResult').text(res.message || 'Error').addClass('text-danger');
    }, function() { $('#simulateGpaResult').text('Request failed.').addClass('text-danger'); });
}

function exportPlanCSV() {
    const codes = getPlanCourseCodes();
    if (codes.length === 0) { showAlert('Add courses to your plan or load recommendations first.', 'warning'); return; }
    const params = new URLSearchParams({ course_codes: codes.join(',') });
    window.location.href = '/api/export/plan/csv?' + params.toString();
}

function exportPlanPDF() {
    const codes = getPlanCourseCodes();
    if (codes.length === 0) { showAlert('Add courses to your plan or load recommendations first.', 'warning'); return; }
    fetch('/api/export/plan/pdf', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/pdf' },
        body: JSON.stringify({ course_codes: codes })
    }).then(function(r) {
        if (!r.ok) return r.json().then(function(j) { throw new Error(j.message || 'Export failed'); });
        return r.blob();
    }).then(function(blob) {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'semester_plan.pdf';
        a.click();
        URL.revokeObjectURL(a.href);
        showAlert('PDF downloaded.', 'success');
    }).catch(function(e) {
        showAlert(e.message || 'PDF export failed. Install reportlab on server for PDF.', 'danger');
    });
}

function syncRecommendationGoalsFields(profile) {
    if (!$('#recCurrentGpaDisplay').length || !profile) {
        return;
    }
    $('#recCurrentGpaDisplay').text(formatGPA(profile.gpa || 0));
    const tol = profile.workload_tolerance != null ? profile.workload_tolerance : 0.5;
    $('#recWorkloadRange').val(tol);
    $('#recWorkloadValue').text(Number(tol).toFixed(1));
    if (profile.target_semester_gpa != null && profile.target_semester_gpa !== undefined) {
        $('#recTargetGpaInput').val(profile.target_semester_gpa);
    } else {
        $('#recTargetGpaInput').val('');
    }
}

function loadRecommendationGoalsFromProfile() {
    API.get('/api/student/profile', function(response) {
        syncRecommendationGoalsFields(response.profile);
    });
}

function loadProfile() {
    API.get('/api/student/profile', function(response) {
        const profile = response.profile;
        $('#gpaDisplay').text(formatGPA(profile.gpa || 0));
        $('#semesterDisplay').text(profile.current_semester || 1);
        syncRecommendationGoalsFields(profile);
        
        const majorCode = profile.major || 'N/A';
        if (majorCode !== 'N/A') {
            API.get('/api/majors', function(majorsResponse) {
                if (majorsResponse.success && majorsResponse.majors) {
                    const major = majorsResponse.majors.find(m => m.code === majorCode);
                    if (major && major.display) {
                        const displayName = major.display.split(' - ')[1] || major.name || majorCode;
                        $('#majorDisplay').text(displayName);
                    } else {
                        $('#majorDisplay').text(majorCode);
                    }
                } else {
                    $('#majorDisplay').text(majorCode);
                }
            }, function() {
                $('#majorDisplay').text(majorCode);
            });
        } else {
            $('#majorDisplay').text('N/A');
        }
        
        if ($('#profileModal').hasClass('show')) {
            $('#strategySelect').val(profile.strategy || 'balanced');
            $('#workloadRange').val(profile.workload_tolerance || 0.5);
            $('#workloadValue').text(profile.workload_tolerance || 0.5);
            $('#currentSemesterInput').val(profile.current_semester || 1);
        }
    }, function(error) {
        console.error('Error loading profile:', error);
    });
}

function loadCompletedCourses() {
    $('#completedCoursesList').html('<div class="text-center py-3"><div class="spinner-border spinner-border-sm" role="status"></div> <small class="d-block mt-2">Loading...</small></div>');
    
    API.get('/api/courses/completed', function(response) {
        const courses = response.courses || [];
        $('#coursesDisplay').text(courses.length);
        
        let html = '';
        if (courses.length === 0) {
            html = '<p class="text-muted">No completed courses yet. Click "Add Course" to add your first course!</p>';
        } else {
            const codes = courses.map(c => c.course_code).filter(Boolean);
            API.get('/api/courses/ratings/batch?course_codes=' + encodeURIComponent(codes.join(',')), function(r) {
                const ratings = (r && r.ratings) ? r.ratings : {};
                let html2 = '';
                courses.forEach(course => {
                    const r = ratings[course.course_code] || {};
                    const avg = r.average != null ? r.average : null;
                    const count = r.count || 0;
                    const userRating = r.user_rating != null ? r.user_rating : '';
                    const ratingLabel = avg != null ? `Student rating: ${avg} (${count})` : (count ? `Rated by ${count}` : '');
                    html2 += `
                        <div class="course-item mb-2 p-2 border rounded" id="course-${course.id}">
                            <div class="d-flex justify-content-between align-items-center flex-wrap">
                                <div class="flex-grow-1">
                                    <strong>${course.course_code || 'N/A'}</strong> - ${course.name || 'N/A'}
                                    <br><small class="text-muted">
                                        Grade: <span id="grade-${course.id}">${course.grade || 'N/A'}</span> 
                                        (${formatGPA(course.grade_points || 0)}) | 
                                        ${course.credit_hours || 0} credits | 
                                        Semester: <span id="semester-${course.id}">${course.semester_taken || 1}</span>
                                        ${ratingLabel ? '<br><span class="rating-display">' + ratingLabel + '</span>' : ''}
                                    </small>
                                    <div class="mt-1 small">
                                        <label class="me-1">Rate difficulty (1=easy, 5=hard):</label>
                                        <select class="form-select form-select-sm d-inline-block w-auto course-rate-select" data-code="${course.course_code}" data-id="${course.id}">
                                            <option value="">--</option>
                                            <option value="1" ${userRating === 1 ? 'selected' : ''}>1</option>
                                            <option value="2" ${userRating === 2 ? 'selected' : ''}>2</option>
                                            <option value="3" ${userRating === 3 ? 'selected' : ''}>3</option>
                                            <option value="4" ${userRating === 4 ? 'selected' : ''}>4</option>
                                            <option value="5" ${userRating === 5 ? 'selected' : ''}>5</option>
                                        </select>
                                    </div>
                                </div>
                                <div class="ms-3">
                                    <button class="btn btn-sm btn-outline-primary me-1" onclick="editCourse(${course.id}, '${course.course_code}', '${(course.name || 'N/A').replace(/'/g, "\\'")}', '${course.grade || 'A'}', ${course.semester_taken || 1})" title="Edit">
                                        <i class="bi bi-pencil"></i>
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger" onclick="deleteCourse(${course.id}, '${course.course_code}')" title="Delete">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                });
                $('#completedCoursesList').html(html2);
                loadAcademicJourneySection();
                $('.course-rate-select').on('change', function() {
                    var code = $(this).data('code');
                    var rating = $(this).val();
                    if (!rating) return;
                    API.post('/api/courses/' + encodeURIComponent(code) + '/rate', { rating: parseInt(rating, 10) }, function() {
                        showAlert('Rating saved.', 'success');
                        loadCompletedCourses();
                    });
                });
            }, function() {
                courses.forEach(function(course) {
                    html += '<div class="course-item mb-2 p-2 border rounded" id="course-' + course.id + '"><div class="d-flex justify-content-between align-items-center"><div class="flex-grow-1"><strong>' + (course.course_code || 'N/A') + '</strong> - ' + (course.name || 'N/A') + '<br><small class="text-muted">Grade: <span id="grade-' + course.id + '">' + (course.grade || 'N/A') + '</span> (' + formatGPA(course.grade_points || 0) + ') | ' + (course.credit_hours || 0) + ' credits | Semester: <span id="semester-' + course.id + '">' + (course.semester_taken || 1) + '</span></small></div><div class="ms-3"><button class="btn btn-sm btn-outline-primary me-1" onclick="editCourse(' + course.id + ', \'' + (course.course_code || '').replace(/'/g, "\\'") + '\', \'' + (course.name || 'N/A').replace(/'/g, "\\'") + '\', \'' + (course.grade || 'A') + '\', ' + (course.semester_taken || 1) + ')" title="Edit"><i class="bi bi-pencil"></i></button><button class="btn btn-sm btn-outline-danger" onclick="deleteCourse(' + course.id + ', \'' + (course.course_code || '') + '\')" title="Delete"><i class="bi bi-trash"></i></button></div></div></div>';
                });
                $('#completedCoursesList').html(html);
                loadAcademicJourneySection();
            });
            return;
        }
        $('#completedCoursesList').html(html);
        loadAcademicJourneySection();
    }, function(error) {
        console.error('Error loading completed courses:', error);
        $('#completedCoursesList').html('<p class="text-danger">Error loading completed courses. Please refresh the page.</p>');
    });
}

function loadUnlockedCourses() {
    $('#unlockedCoursesList').html('<div class="text-center py-3"><div class="spinner-border spinner-border-sm" role="status"></div> <small class="d-block mt-2">Loading...</small></div>');

    API.get('/api/courses/unlocked?limit=200', function(response) {
        const courses = response.courses || [];

        let html = '';
        if (courses.length === 0) {
            html = '<p class="text-muted">No unlocked courses available for your major. Complete prerequisite courses first!</p>';
        } else {
            html = `<div class="mb-2"><strong>${courses.length} unlocked courses</strong> <small class="text-muted">(Showing first 50)</small></div>`;
            courses.slice(0, 50).forEach(course => {
                const courseCode = course.course_code || '';
                if (!courseCode || courseCode === 'N/A') return;

                    const badge = formatCatalogRoleBadge(course);
                    const escapedCode = courseCode.replace(/'/g, "\\'");
                html += `
                    <div class="course-item mb-2 p-2 border rounded">
                        <div class="d-flex justify-content-between align-items-center">
                            <div class="flex-grow-1">
                                <strong>${courseCode}</strong>${badge} - ${course.name || 'N/A'}
                                <br><small class="text-muted">${course.credit_hours || 0} credits | Level ${course.course_level || 100} | ${course.subject || ''}</small>
                            </div>
                            <div class="ms-3">
                                <button class="btn btn-sm btn-outline-primary" onclick="getCourseDifficulty('${escapedCode}', this)" title="Get difficulty prediction">
                                    <i class="bi bi-graph-up"></i> Difficulty
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        $('#unlockedCoursesList').html(html);
    }, function(error) {
        console.error('Error loading unlocked courses:', error);
        $('#unlockedCoursesList').html('<p class="text-danger">Error loading unlocked courses. Please refresh the page.</p>');
    });
}

function loadRecommendations() {
    const targetCredits = parseInt($('#targetCredits').val()) || 15;
    const maxCourses = parseInt($('#maxCourses').val()) || 6;
    const term = $('#termSelect').val() || 'Fall';

    const tol = parseFloat($('#recWorkloadRange').val());
    const tgtRaw = $('#recTargetGpaInput').val();

    if ($('#recWorkloadRange').length && (isNaN(tol) || tol < 0 || tol > 1)) {
        showAlert('Set semester intensity (tolerance) between 0 and 1.', 'warning');
        return;
    }

    const payload = {};
    if ($('#recWorkloadRange').length) {
        payload.workload_tolerance = tol;
        if (tgtRaw !== '' && tgtRaw != null) {
            const tg = parseFloat(tgtRaw);
            if (!isNaN(tg) && tg >= 0 && tg <= 4) {
                payload.target_semester_gpa = tg;
            }
        } else {
            payload.target_semester_gpa = null;
        }
    }

    $('#recommendationsList').html('<div class="text-center"><div class="spinner-border" role="status"></div> <p class="mt-2">Saving goals and loading recommendations...</p></div>');
    $('#plannerTableContainer').hide();

    const runFetch = function() {
        let recoUrl = `/api/recommendations?credits=${targetCredits}&max_courses=${maxCourses}&term=${encodeURIComponent(term)}`;
        if ($('#recWorkloadRange').length && !isNaN(tol)) {
            recoUrl += `&tolerance=${encodeURIComponent(tol)}`;
        }
        if (tgtRaw !== '' && tgtRaw != null) {
            const tg = parseFloat(tgtRaw);
            if (!isNaN(tg) && tg >= 0 && tg <= 4) {
                recoUrl += `&target_gpa=${encodeURIComponent(tg)}`;
            }
        }
        if ($('#recIncludeElectives').length) {
            recoUrl += `&include_electives=${$('#recIncludeElectives').is(':checked') ? '1' : '0'}`;
        }
        if ($('#recElectiveEmphasis').length) {
            recoUrl += `&elective_emphasis=${encodeURIComponent($('#recElectiveEmphasis').val() || 'balanced')}`;
        }
        if ($('#recMaxHardCourses').length) {
            const mh = $('#recMaxHardCourses').val();
            if (mh !== '' && mh != null) {
                recoUrl += `&max_hard=${encodeURIComponent(mh)}`;
            }
        }
        recoUrl += `&_=${Date.now()}`;
        API.get(recoUrl, function(response) {
        const recommendations = response.recommendations || [];
        const term = response.term || 'Fall';
        
        currentRecommendations = recommendations.filter(c => parseFloat(c.credit_hours || 0) > 0);
        
        if (recommendations.length > 0) {
            let tableHtml = '';
            let totalCredits = 0;
            
            recommendations.forEach((course, index) => {
                const difficulty = course.difficulty_score || 0.5;
                const diff = formatDifficulty(difficulty);
                const diffPercent = (difficulty * 100).toFixed(0);
                const creditHours = parseFloat(course.credit_hours || 0);
                if (creditHours <= 0) return;
                totalCredits += creditHours;
                
                const labB = labBadgeHtml(course);
                const roleBadge = formatCatalogRoleBadge(course);
                
                tableHtml += `
                    <tr>
                        <td><strong>${course.course_code || 'N/A'}</strong>${labB}</td>
                        <td>${course.name || 'N/A'}</td>
                        <td>${creditHours}</td>
                        <td>
                            <span class="difficulty-badge ${diff.class}">${diff.text}</span>
                            <small class="text-muted">(${diffPercent}%)</small>
                        </td>
                        <td>${course.course_level || 100}</td>
                        <td>${roleBadge}<br><small class="text-muted">${course.subject || ''}</small></td>
                    </tr>
                `;
            });
            
            $('#plannerTableBody').html(tableHtml);
            $('#plannerTotalCredits').text(`${totalCredits.toFixed(1)} credits`);
            $('#plannerTotalCourses').text(`${recommendations.filter(c => parseFloat(c.credit_hours || 0) > 0).length} courses`);
            $('#plannerTableContainer').show();
        } else {
            $('#plannerTableContainer').hide();
        }
        
        let html = '';
        if (recommendations.length === 0) {
            html = `
                <div class="alert alert-info">
                    <i class="bi bi-info-circle"></i> <strong>No recommendations available.</strong>
                    <br><small>This could mean:
                    <ul class="mb-0 mt-2">
                        <li>You've completed all available courses for your major</li>
                        <li>No courses are currently unlocked (complete prerequisites first)</li>
                        <li>Try adjusting your target credits or complete more courses</li>
                    </ul>
                    </small>
                </div>
            `;
            if (response.planning_params) {
                const p = response.planning_params;
                if (p.credit_warning) {
                    html += `<div class="alert alert-warning small mb-0 mt-2"><i class="bi bi-exclamation-triangle"></i> ${p.credit_warning}</div>`;
                }
            }
            if (response.alternatives && response.alternatives.length > 0) {
                html += '<div class="mt-3"><h6 class="text-muted small text-uppercase">Also consider (alternates)</h6><ul class="small mb-0">';
                response.alternatives.forEach(function(alt) {
                    const pct = alt.difficulty_score != null ? (Number(alt.difficulty_score) * 100).toFixed(0) : '—';
                    html += `<li><strong>${alt.course_code || ''}</strong> — ${alt.name || ''}</li>`;
                });
                html += '</ul></div>';
            }
        } else {
            html = `<div class="alert alert-success mb-3 border-0 shadow-sm"><i class="bi bi-check-circle-fill"></i> <strong>${recommendations.filter(c => parseFloat(c.credit_hours || 0) > 0).length} courses recommended for ${term} semester</strong></div>`;
            if (response.planning_params) {
                const p = response.planning_params;
                const tol = p.workload_tolerance != null ? Number(p.workload_tolerance).toFixed(1) : '—';
                const slack = p.credit_slack != null ? p.credit_slack : '—';
                const maxCr = p.effective_max_credits != null ? Number(p.effective_max_credits).toFixed(0) : '—';
                const mh = p.max_hard_courses != null ? p.max_hard_courses : '—';
                const emc = p.effective_max_courses != null ? p.effective_max_courses : '—';
                const tg = p.target_semester_gpa != null ? ` · Target GPA: ${Number(p.target_semester_gpa).toFixed(2)}` : '';
                const cg = p.current_gpa != null ? ` · GPA now: ${Number(p.current_gpa).toFixed(2)}` : '';
                const gm = p.goal_mode ? ` · Plan mode: ${String(p.goal_mode).replace(/_/g, ' ')}` : '';
                const ew = p.easy_preference_weight != null ? ` · Safety weight: ${Number(p.easy_preference_weight).toFixed(2)}` : '';
                const ts = p.total_credits_scheduled != null ? ` · Scheduled: ${Number(p.total_credits_scheduled).toFixed(1)} cr (cap ${maxCr})` : '';
                const ecap = p.elective_credit_cap != null && p.elective_credits_in_plan != null
                    ? ` · Elective-pool credits: ${Number(p.elective_credits_in_plan).toFixed(1)} / ${Number(p.elective_credit_cap).toFixed(0)} cap`
                    : '';
                const incEl = p.include_electives === false ? ' · electives off' : '';
                const emLb = p.elective_emphasis ? ` · mix: ${String(p.elective_emphasis).replace(/_/g, ' ')}` : '';
                const mhSrc = p.max_hard_source === 'override' ? ' (you set)' : '';
                const wm = p.workload_model ? `<span class="d-block mt-1 text-muted">${p.workload_model}</span>` : '';
                html += `<div class="alert rec-alert-soft small mb-3"><strong class="text-body">Plan summary:</strong> intensity ${tol}${cg}${tg}${gm} · up to ${emc} courses · credit cap ${maxCr}${ts} · flex index ${slack} · max Hard: ${mh}${mhSrc}${ew}${ecap}${incEl}${emLb}${wm}</div>`;
                if (p.credit_warning) {
                    html += `<div class="alert alert-warning small mb-3"><i class="bi bi-exclamation-triangle"></i> ${p.credit_warning}</div>`;
                }
            }
            if (response.alternatives && response.alternatives.length > 0) {
                html += '<div class="mb-3"><h6 class="text-muted small text-uppercase">Also consider (alternates)</h6><ul class="small mb-0">';
                response.alternatives.forEach(function(alt) {
                    const pct = alt.difficulty_score != null ? (Number(alt.difficulty_score) * 100).toFixed(0) : '—';
                    const b = alt.catalog_bucket ? ` · ${alt.catalog_bucket}` : '';
                    html += `<li><strong>${alt.course_code || ''}</strong> — ${alt.name || ''} (${alt.credit_hours || 0} cr, ~${pct}% diff${b})</li>`;
                });
                html += '</ul></div>';
            }
            if (response.semester_workload) {
                const w = response.semester_workload;
                const sd = w.semester_difficulty != null ? Number(w.semester_difficulty).toFixed(2) : '—';
                const or = w.overload_risk != null ? Number(w.overload_risk).toFixed(2) : '—';
                html += `<div class="alert rec-alert-soft small mb-3"><strong class="text-body">ML semester workload:</strong> difficulty ${sd} · overload risk ${or}</div>`;
            }
            recommendations.forEach(course => {
                const difficulty = course.difficulty_score || 0.5;
                const diff = formatDifficulty(difficulty);
                const diffPercent = (difficulty * 100).toFixed(0);
                const creditHours = parseFloat(course.credit_hours || 0);
                
                if (creditHours <= 0) return;
                
                const labB = labBadgeHtml(course);
                const roleB = formatCatalogRoleBadge(course);
                const roleRowClass = catalogRoleItemClass(course);
                
                html += `
                    <div class="course-item mb-2 p-2 border rounded ${roleRowClass}">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <strong>${course.course_code || 'N/A'}</strong> ${roleB}${labB}
                                <br><small class="text-muted">${course.name || 'N/A'}</small>
                                <br><small class="text-muted">${creditHours} credits | Level ${course.course_level || 100} | ${course.subject || 'N/A'}</small>
                            </div>
                            <div class="text-end ms-3">
                                <span class="difficulty-badge ${diff.class}">${diff.text}</span>
                                <br><small class="text-muted">${diffPercent}%</small>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        $('#recommendationsList').html(html);
        }, function(error) {
            console.error('Error loading recommendations:', error);
            $('#recommendationsList').html(`
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> <strong>Error loading recommendations.</strong>
                    <br><small>Please try again or refresh the page.</small>
                </div>
            `);
            $('#plannerTableContainer').hide();
        });
    };

    if (Object.keys(payload).length > 0) {
        API.post('/api/student/profile', payload, function(pr) {
            if (!pr || !pr.success) {
                $('#recommendationsList').html(`
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle"></i> <strong>Could not save your goals.</strong>
                        <br><small>Check your target GPA (0–4) and try again.</small>
                    </div>
                `);
                return;
            }
            runFetch();
        }, function() {
            $('#recommendationsList').html(`
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> <strong>Network error while saving goals.</strong>
                </div>
            `);
        });
    } else {
        runFetch();
    }
}

function loadBottlenecks() {
    $('#bottlenecksList').html('<div class="text-center py-3"><div class="spinner-border spinner-border-sm" role="status"></div> <small class="d-block mt-2">Loading courses...</small></div>');
    
    API.get('/api/advisor/bottlenecks', function(response) {
        const bottlenecks = response.bottlenecks || [];
        
        let html = '';
        if (bottlenecks.length === 0) {
            html = '<div class="alert alert-info"><i class="bi bi-info-circle"></i> No courses found. Complete some courses first!</div>';
        } else {
            const unlocked = bottlenecks.filter(c => c.is_unlocked);
            const locked = bottlenecks.filter(c => !c.is_unlocked);
            
            if (unlocked.length > 0) {
                html += `<div class="mb-4">
                    <h6 class="text-success mb-3"><i class="bi bi-check-circle-fill"></i> Courses You Can Take Now (${unlocked.length})</h6>
                    <p class="text-muted small mb-2">Based on your completed courses, you can take these courses:</p>
                    <p class="text-muted small mb-3"><i class="bi bi-info-circle"></i> <strong>Unlocks</strong> counts how many courses list this code as a <em>direct</em> prerequisite. Downstream courses still need their other prerequisites satisfied.</p>`;
                
                unlocked.slice(0, 12).forEach((course, index) => {
                    const unlocksCount = course.unlocks_count || 0;
                    const priorityIcon = index < 3 ? '<i class="bi bi-star-fill text-warning"></i> ' : '';
                    
                    html += `
                        <div class="course-item mb-3 p-3 border-start border-success border-4" style="background: linear-gradient(to right, #f0fdf4 0%, white 20%);">
                            <div class="d-flex justify-content-between align-items-start flex-wrap">
                                <div class="flex-grow-1">
                                    <div class="d-flex align-items-center mb-2 flex-wrap gap-2">
                                        <h6 class="mb-0">${priorityIcon}<strong>${course.course_code || 'N/A'}</strong></h6>
                                        <span class="badge bg-success"><i class="bi bi-check-circle"></i> Available Now</span>
                                    </div>
                                    <p class="mb-2 fw-semibold">${course.name || 'N/A'}</p>
                                    <div class="d-flex align-items-center gap-2 flex-wrap">
                                        <span class="badge bg-primary">
                                            <i class="bi bi-box-arrow-up"></i> Unlocks ${unlocksCount} courses
                                        </span>
                                        <span class="badge bg-secondary">${course.credit_hours || 3} credits</span>
                                        <span class="badge bg-info">Level ${course.course_level || 100}</span>
                                    </div>
                                    ${course.prerequisites && course.prerequisites.length > 0 ? 
                                        `<div class="mt-2"><small class="text-success"><i class="bi bi-check2"></i> <strong>Prerequisites met:</strong> ${course.prerequisites.join(', ')}</small></div>` : 
                                        '<div class="mt-2"><small class="text-success"><i class="bi bi-check2"></i> No prerequisites required</small></div>'}
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
            }
            
            if (locked.length > 0) {
                html += `<div class="mt-4">
                    <h6 class="text-warning mb-3"><i class="bi bi-exclamation-triangle-fill"></i> High-Impact Bottleneck Courses (${locked.length})</h6>
                    <p class="text-muted small mb-3">These courses unlock many others. Complete prerequisites to access them:</p>`;
                
                locked.slice(0, 12).forEach((course, index) => {
                    const unlocksCount = course.unlocks_count || 0;
                    const priorityIcon = index < 3 ? '<i class="bi bi-star-fill text-warning"></i> ' : '';
                    
                    html += `
                        <div class="course-item mb-3 p-3 border-start border-warning border-4" style="background: linear-gradient(to right, #fffbeb 0%, white 20%);">
                            <div class="d-flex justify-content-between align-items-start flex-wrap">
                                <div class="flex-grow-1">
                                    <div class="d-flex align-items-center mb-2 flex-wrap gap-2">
                                        <h6 class="mb-0">${priorityIcon}<strong>${course.course_code || 'N/A'}</strong></h6>
                                        <span class="badge bg-warning text-dark"><i class="bi bi-lock"></i> Locked</span>
                                    </div>
                                    <p class="mb-2 fw-semibold">${course.name || 'N/A'}</p>
                                    <div class="d-flex align-items-center gap-2 flex-wrap">
                                        <span class="badge bg-primary">
                                            <i class="bi bi-box-arrow-up"></i> Unlocks ${unlocksCount} courses
                                        </span>
                                        <span class="badge bg-secondary">${course.credit_hours || 3} credits</span>
                                        <span class="badge bg-info">Level ${course.course_level || 100}</span>
                                    </div>
                                    ${course.missing_prerequisites && course.missing_prerequisites.length > 0 ? 
                                        `<div class="mt-2"><small class="text-warning"><i class="bi bi-x-circle"></i> <strong>Missing prerequisites:</strong> ${course.missing_prerequisites.join(', ')}</small></div>` : 
                                        ''}
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
            }
        }
        $('#bottlenecksList').html(html);
    }, function(error) {
        console.error('Error loading bottlenecks:', error);
        $('#bottlenecksList').html('<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Error loading courses. Please refresh the page.</div>');
    });
}

function showProfileModal() {
    API.get('/api/majors', function(response) {
        if (response.success) {
            const select = $('#majorSelect');
            select.empty();
            response.majors.forEach(function(major) {
                select.append(`<option value="${major.code}">${major.display}</option>`);
            });
            
            API.get('/api/student/profile', function(profileResponse) {
                const profile = profileResponse.profile;
                select.val(profile.major || 'ECE');
                $('#strategySelect').val(profile.strategy || 'balanced');
                $('#workloadRange').val(profile.workload_tolerance || 0.5);
                $('#workloadValue').text(profile.workload_tolerance || 0.5);
                $('#currentSemesterInput').val(profile.current_semester || 1);
                if (profile.target_semester_gpa != null && profile.target_semester_gpa !== undefined) {
                    $('#targetSemesterGpaInput').val(profile.target_semester_gpa);
                } else {
                    $('#targetSemesterGpaInput').val('');
                }
            });
        }
    }, function(error) {
        console.error('Error loading majors:', error);
    });
    
    const modal = new bootstrap.Modal(document.getElementById('profileModal'));
    modal.show();
}

function saveProfile() {
    const saveBtn = document.querySelector('#profileModal .btn-primary');
    if (saveBtn.disabled) return;
    
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
    
    const tgtRaw = $('#targetSemesterGpaInput').val();
    const data = {
        major: major,
        current_semester: currentSemester,
        strategy: strategy,
        workload_tolerance: workloadTolerance
    };
    if (tgtRaw !== '' && tgtRaw != null) {
        const tg = parseFloat(tgtRaw);
        if (!isNaN(tg) && tg >= 0 && tg <= 4) {
            data.target_semester_gpa = tg;
        }
    } else {
        data.target_semester_gpa = null;
    }
    
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
    
    API.post('/api/student/profile', data, function(response) {
        if (response && response.success) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('profileModal'));
            if (modal) {
                modal.hide();
            }
            loadProfile();
            loadUnlockedCourses();
            loadAvailableCourses();
            loadRecommendations();
            loadBottlenecks();
            showAlert('Profile updated successfully!', 'success');
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
    
}

/** Add-course modal: full list from API + active type filter (major / elective / supporting). */
var addCourseModalCatalog = { courses: [] };

function addCourseCatalogTag(course) {
    return catalogBucket(course);
}

function renderAddCourseCatalogList() {
    const all = addCourseModalCatalog.courses;
    const filter = $('input[name="addCourseCatalogFilter"]:checked').val() || 'all';
    const filtered = filter === 'all' ? all.slice() : all.filter(function (c) {
        return addCourseCatalogTag(c) === filter;
    });

    function countTag(tag) {
        return all.filter(function (c) { return addCourseCatalogTag(c) === tag; }).length;
    }
    $('#acfCountAll').text(all.length);
    $('#acfCountMajor').text(countTag('major'));
    $('#acfCountElective').text(countTag('elective'));
    $('#acfCountSupport').text(countTag('support'));

    let html = '';
    if (all.length === 0) {
        const q = $('#courseSearchInput').val().trim();
        html = q.length >= 2
            ? '<p class="text-muted">No courses match your search, or all matches are already completed.</p>'
            : '<p class="text-muted">No courses loaded. Set your major in profile, or try a search.</p>';
        $('#acfCountAll').text('0');
        $('#acfCountMajor').text('0');
        $('#acfCountElective').text('0');
        $('#acfCountSupport').text('0');
        $('#courseSearchResults').html(html);
        return;
    }
    if (filtered.length === 0) {
        html = '<p class="text-muted">No courses in this category. Try <strong>All</strong> or another type.</p>';
        $('#courseSearchResults').html(html);
        return;
    }

    const label = filter === 'all' ? 'Showing all types' : (filter === 'major' ? 'Major only' : (filter === 'elective' ? 'Electives only' : 'Supporting only'));
    html = `<div class="mb-2"><strong>${filtered.length}</strong> of ${all.length} <small class="text-muted">(${label} — completed hidden)</small></div>`;
    html += '<div style="max-height: 400px; overflow-y: auto; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px;">';

    filtered.forEach(function (course) {
const tag = addCourseCatalogTag(course);
const badge = formatCatalogRoleBadge(course);
        html += `
            <div class="course-item mb-2 p-2 border rounded" style="cursor: pointer; transition: all 0.2s;"
                 onmouseover="this.style.backgroundColor='#f8f9fa'"
                 onmouseout="this.style.backgroundColor='white'"
                 onclick="selectCourse('${course.course_code}', '${(course.name || 'N/A').replace(/'/g, "\\'")}')">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${course.course_code}</strong>${badge}
                        <br><small class="text-muted">${course.name || 'N/A'}</small>
                        <br><small class="text-muted">${course.credit_hours} credits | Level ${course.course_level}</small>
                    </div>
                    <i class="bi bi-chevron-right text-primary"></i>
                </div>
            </div>
        `;
    });
    html += '</div>';
    $('#courseSearchResults').html(html);
}

function setAddCourseCatalogCourses(courses) {
    addCourseModalCatalog.courses = courses || [];
    renderAddCourseCatalogList();
}

function showAddCourseModal() {
    const modal = new bootstrap.Modal(document.getElementById('addCourseModal'));
    modal.show();

    $('#courseSearchInput').val('');
    $('#acfAll').prop('checked', true);
    addCourseModalCatalog.courses = [];
    $('#courseSearchResults').html('<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div> Loading courses...</div>');
    $('#addCourseForm').hide();
    $('#addCourseBtn').hide();
    $('#addCourseCatalogFilterWrap').show();

    loadAllMajorCourses();

    $('#addCourseModal').on('shown.bs.modal', function () {
        $('#courseSearchInput').focus();
    });
}

function loadAllMajorCourses() {
    API.get('/api/courses/completed', function (completedResponse) {
        const completedCourses = (completedResponse.courses || []).map(function (c) { return c.course_code; });

        API.get('/api/courses/search', function (response) {
            const courses = (response.courses || []).filter(function (c) {
                return !completedCourses.includes(c.course_code);
            });
            setAddCourseCatalogCourses(courses);
        }, function (error) {
            console.error('Error loading courses:', error);
            $('#courseSearchResults').html('<p class="text-danger">Error loading courses. Please try again.</p>');
        });
    }, function (error) {
        API.get('/api/courses/search', function (response) {
            setAddCourseCatalogCourses(response.courses || []);
        });
    });
}

$(document).on('change', 'input[name="addCourseCatalogFilter"]', function () {
    if (addCourseModalCatalog.courses.length) {
        renderAddCourseCatalogList();
    }
});

$('#courseSearchInput').on('input', function () {
    const query = $(this).val().trim();

    if (query.length >= 2) {
        $('#courseSearchResults').html('<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> Searching...</div>');

        API.get('/api/courses/completed', function (completedResponse) {
            const completedCourses = (completedResponse.courses || []).map(function (c) { return c.course_code; });

            API.get('/api/courses/search?q=' + encodeURIComponent(query), function (response) {
                const courses = (response.courses || []).filter(function (c) {
                    return !completedCourses.includes(c.course_code);
                });
                setAddCourseCatalogCourses(courses.slice(0, 200));
            }, function (error) {
                $('#courseSearchResults').html('<p class="text-danger">Error searching courses. Please try again.</p>');
            });
        });
    } else if (query.length === 0) {
        loadAllMajorCourses();
    }
});

function addCoursePickAnother() {
    $('#selectedCourseCode').val('');
    $('#addCourseForm').hide();
    $('#addCourseBtn').hide();
    $('#addCourseCatalogFilterWrap').show();
    loadAllMajorCourses();
}

function selectCourse(courseCode, courseName) {
    $('#selectedCourseCode').val(courseCode);
    $('#addCourseForm').show();
    $('#addCourseBtn').show();
    $('#addCourseCatalogFilterWrap').hide();
    $('#courseSearchResults').html(
        '<div class="alert alert-success mb-0">' +
        '<i class="bi bi-check-circle"></i> <strong>Selected:</strong> ' + courseCode + ' - ' + courseName +
        '<br><small>Fill in the grade and semester below, then click &quot;Add Course&quot;</small>' +
        '<div class="mt-2">' +
        '<button type="button" class="btn btn-sm btn-outline-secondary" onclick="addCoursePickAnother()">' +
        '<i class="bi bi-arrow-left"></i> Choose a different course</button>' +
        '</div></div>'
    );

    $('#addCourseForm')[0].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function addCourse() {
    const courseCode = $('#selectedCourseCode').val();
    const grade = $('#courseGrade').val();
    const semesterTaken = parseInt($('#semesterTaken').val());
    
    if (!courseCode) {
        showAlert('Please select a course first', 'warning');
        return;
    }
    
    if (!grade) {
        showAlert('Please select a grade', 'warning');
        return;
    }
    
    if (isNaN(semesterTaken) || semesterTaken < 1) {
        showAlert('Please enter a valid semester (1 or higher)', 'warning');
        return;
    }
    
    const data = {
        course_code: courseCode,
        grade: grade,
        semester_taken: semesterTaken
    };
    
    const addBtn = document.getElementById('addCourseBtn');
    const originalText = addBtn.innerHTML;
    addBtn.disabled = true;
    addBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding...';
    
    API.post('/api/courses/completed', data, function(response) {
        const modal = bootstrap.Modal.getInstance(document.getElementById('addCourseModal'));
        if (modal) {
            modal.hide();
        }
        $('#courseSearchInput').val('');
        $('#selectedCourseCode').val('');
        $('#addCourseForm').hide();
        $('#addCourseBtn').hide();
        $('#courseGrade').val('A');
        $('#semesterTaken').val('1');
        
        loadCompletedCourses();
        loadUnlockedCourses();
        loadProfile();
        loadRecommendations();
        loadBottlenecks();
        loadAvailableCourses();
        if (typeof loadAIInsights === 'function') {
            loadAIInsights();
        }
        showAlert('Course added successfully!', 'success');
    }, function(error) {
        console.error('Error adding course:', error);
        if (error && error.prerequisite_error) {
            const msg = error.user_message || error.message
                || 'Complete the required prerequisite course(s) in My Courses before adding this course.';
            showMessageBox('Prerequisites required', msg, 'warning');
            return;
        }
        if (error && (error.duplicate || (error.message && error.message.includes('already')))) {
            showAlert(`This course is already in your completed courses. You cannot add the same course multiple times. Edit or remove it from "My Courses" tab.`, 'warning');
            setTimeout(() => {
                loadCompletedCourses();
                const coursesTab = document.querySelector('[data-bs-target="#courses"]');
                if (coursesTab) {
                    coursesTab.click();
                }
            }, 500);
        } else {
            const errorMsg = error && error.message ? error.message : 'Failed to add course. Please try again.';
            showAlert(errorMsg, 'danger');
        }
    });
    
    setTimeout(() => {
        addBtn.disabled = false;
        addBtn.innerHTML = originalText;
    }, 2000);
}

function searchCourses(query) {
    if (!query || query.length < 2) {
        $('#plannerSearchResults').html('');
        return;
    }
    
    $('#plannerSearchResults').html('<div class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> Searching...</div>');
    
    API.get(`/api/courses/search?q=${encodeURIComponent(query)}`, function(response) {
        const courses = response.courses || [];
        let html = '';
        
        if (courses.length === 0) {
            html = '<p class="text-muted">No courses found matching your search.</p>';
        } else {
            html = `<div class="mb-2"><strong>${courses.length} courses found</strong> <small class="text-muted">(Click to add)</small></div>`;
            html += '<div style="max-height: 300px; overflow-y: auto; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px;">';
            
            courses.slice(0, 20).forEach(course => {
                if (selectedCourses.find(c => c.code === course.course_code)) {
                    return;
                }
                
                    const badge = formatCatalogRoleBadge(course);
                html += `
                    <div class="course-item mb-2 p-2 border rounded" style="cursor: pointer; transition: all 0.2s;" 
                         onmouseover="this.style.backgroundColor='#f8f9fa'" 
                         onmouseout="this.style.backgroundColor='white'"
                         onclick="addToPlanner('${course.course_code}', '${(course.name || 'N/A').replace(/'/g, "\\'")}')">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong>${course.course_code}</strong>${badge}
                                <br><small class="text-muted">${course.name || 'N/A'}</small>
                                <br><small class="text-muted">${course.credit_hours || 0} credits | Level ${course.course_level || 100}</small>
                            </div>
                            <i class="bi bi-plus-circle text-success"></i>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }
        
        $('#plannerSearchResults').html(html);
    }, function(error) {
        console.error('Error searching courses:', error);
        $('#plannerSearchResults').html('<p class="text-danger">Error searching courses. Please try again.</p>');
    });
}

function addToPlanner(courseCode, courseName) {
    if (!selectedCourses.find(c => c.code === courseCode)) {
        API.get(`/api/courses/search?q=${encodeURIComponent(courseCode)}`, function(response) {
            const courses = response.courses || [];
            const course = courses.find(c => c.course_code === courseCode);
            const credits = course ? course.credit_hours : 3;
            
            selectedCourses.push({ 
                code: courseCode, 
                name: courseName,
                credits: credits
            });
            updateSelectedCourses();
            
            $('#courseSearch').val('');
            $('#plannerSearchResults').html(`<div class="alert alert-success alert-dismissible fade show" role="alert">
                <i class="bi bi-check-circle"></i> Added <strong>${courseCode}</strong> to planner
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>`);
        }, function() {
            selectedCourses.push({ 
                code: courseCode, 
                name: courseName,
                credits: 3
            });
            updateSelectedCourses();
        });
    } else {
        showAlert('Course already in planner', 'info');
    }
}

function updateSelectedCourses() {
    let html = '';
    if (selectedCourses.length === 0) {
        html = '<p class="text-muted">No courses selected. Search and click courses above to add them.</p>';
    } else {
        let totalCredits = 0;
        selectedCourses.forEach(course => {
            const credits = course.credits || 3;
            totalCredits += credits;
            html += `
                <div class="course-item mb-2 p-2 border rounded bg-white">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${course.code}</strong>
                            <br><small class="text-muted">${course.name || 'N/A'}</small>
                            <br><small class="text-muted">${credits} credits</small>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" onclick="removeFromPlanner('${course.code}')" title="Remove">
                            <i class="bi bi-x"></i>
                        </button>
                    </div>
                </div>
            `;
        });
        html += `<hr><p class="mb-0"><strong>Total Credits:</strong> ${totalCredits}</p>`;
    }
    $('#selectedCourses').html(html);
    let simHtml = '';
    selectedCourses.forEach(c => {
        simHtml += `<div class="d-inline-block me-3 mb-1"><label class="me-1">${c.code}</label><select class="form-select form-select-sm d-inline-block w-auto simulate-grade" data-code="${c.code}"><option value="A">A</option><option value="A-">A-</option><option value="B+">B+</option><option value="B">B</option><option value="B-">B-</option><option value="C+">C+</option><option value="C">C</option><option value="C-">C-</option><option value="D">D</option><option value="F">F</option></select></div>`;
    });
    $('#simulateGradesContainer').html(simHtml || '<span class="text-muted">Select courses in the planner first.</span>');
}

function removeFromPlanner(courseCode) {
    selectedCourses = selectedCourses.filter(c => c.code !== courseCode);
    updateSelectedCourses();
}

function addRecommendedCourses() {
    if (!currentRecommendations || currentRecommendations.length === 0) {
        showAlert('No recommendations available. Please load recommendations first from the Recommendations tab.', 'warning');
        return;
    }
    
    let addedCount = 0;
    let skippedCount = 0;
    
    currentRecommendations.forEach(course => {
        const courseCode = course.course_code;
        const courseName = course.name || 'N/A';
        const credits = parseFloat(course.credit_hours || 0) || 3;
        
        if (selectedCourses.find(c => c.code === courseCode)) {
            skippedCount++;
            return;
        }
        
        selectedCourses.push({
            code: courseCode,
            name: courseName,
            credits: credits
        });
        addedCount++;
    });
    
    updateSelectedCourses();
    
    if (addedCount > 0) {
        showAlert(`Added ${addedCount} recommended course${addedCount > 1 ? 's' : ''} to planner${skippedCount > 0 ? ` (${skippedCount} already in planner)` : ''}`, 'success');
    } else if (skippedCount > 0) {
        showAlert('All recommended courses are already in the planner.', 'info');
    } else {
        showAlert('No courses were added. Please check recommendations first.', 'warning');
    }
}

function clearPlanner() {
    if (selectedCourses.length === 0) {
        showAlert('Planner is already empty.', 'info');
        return;
    }
    
    if (confirm(`Are you sure you want to remove all ${selectedCourses.length} course(s) from the planner?`)) {
        selectedCourses = [];
        updateSelectedCourses();
        $('#semesterAnalysis').html('<p class="text-muted">Select courses and click "Analyze Semester" to see predictions.</p>');
        showAlert('Planner cleared.', 'success');
    }
}

function analyzeSemester() {
    if (selectedCourses.length === 0) {
        showAlert('Please select at least one course', 'warning');
        return;
    }
    
    $('#semesterAnalysis').html('<div class="text-center"><div class="spinner-border" role="status"></div> <p class="mt-2">Analyzing semester...</p></div>');
    
    const courseCodes = selectedCourses.map(c => c.code).filter(code => code && code !== 'N/A');
    
    if (courseCodes.length === 0) {
        $('#semesterAnalysis').html('<div class="alert alert-warning">No valid courses selected.</div>');
        return;
    }
    
    API.post('/api/semester/optimize', { course_codes: courseCodes }, function(response) {
        if (!response || !response.success) {
            $('#semesterAnalysis').html(`
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle"></i> <strong>Analysis incomplete.</strong>
                    <br><small>${response.message || 'Unable to complete analysis. Showing basic info.'}</small>
                </div>
            `);
            return;
        }
        
        const analysis = response.analysis;
        if (!analysis) {
            $('#semesterAnalysis').html('<div class="alert alert-warning">Unable to analyze semester. Please try again.</div>');
            return;
        }
        
        const diff = formatDifficulty(analysis.semester_difficulty || 0.5);
        const riskPercent = ((analysis.overload_risk || 0.5) * 100).toFixed(0);
        const riskClass = riskPercent < 30 ? 'bg-success' : riskPercent < 60 ? 'bg-warning' : 'bg-danger';
        
        let html = `
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title"><i class="bi bi-graph-up"></i> Semester Analysis</h5>
                    <hr>
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <p><strong>Total Credits:</strong> ${analysis.total_credits || 0}</p>
                            <p><strong>Number of Courses:</strong> ${analysis.num_courses || selectedCourses.length}</p>
                            <p><strong>Lab Courses:</strong> ${analysis.num_labs || 0}</p>
                        </div>
                        <div class="col-md-6">
                            <p><strong>Difficulty:</strong> <span class="difficulty-badge ${diff.class}">${diff.text}</span></p>
                            <p><strong>Overload Risk:</strong> 
                                <span class="badge ${riskClass}">${riskPercent}%</span>
                            </p>
                        </div>
                    </div>
                    <hr>
                    <h6>Analysis:</h6>
                    <div class="alert alert-info">
                        <pre style="white-space: pre-wrap; font-size: 0.9rem; margin: 0;">${analysis.explanation || 'Analysis completed successfully.'}</pre>
                    </div>
                </div>
            </div>
        `;
        $('#semesterAnalysis').html(html);
    }, function(error) {
        console.error('Error analyzing semester:', error);
        let errorMsg = 'Unknown error occurred';
        if (error && error.message) {
            errorMsg = error.message;
        } else if (error && error.responseJSON && error.responseJSON.message) {
            errorMsg = error.responseJSON.message;
        } else if (typeof error === 'string') {
            errorMsg = error;
        }
        $('#semesterAnalysis').html(`
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> <strong>Error analyzing semester.</strong>
                <br><small>${errorMsg}</small>
                <br><small>Please try again or select different courses.</small>
            </div>
        `);
    });
}

function getCourseDifficulty(courseCode, buttonElement) {
    if (!courseCode || courseCode === 'N/A') {
        showAlert('Course code is required', 'warning');
        return;
    }
    
    const btn = buttonElement || document.querySelector(`button[onclick*="getCourseDifficulty('${courseCode}')"]`);
    let originalText = '';
    if (btn) {
        originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }
    
    API.get(`/api/courses/${encodeURIComponent(courseCode)}/difficulty`, function(response) {
        const difficulty = response.difficulty;
        if (difficulty && difficulty.difficulty_score !== undefined) {
            const diff = formatDifficulty(difficulty.difficulty_score);
            const score = (difficulty.difficulty_score * 100).toFixed(0);
            const category = difficulty.difficulty_category || diff.text;
            
            showAlert(
                `<strong>${courseCode} Difficulty</strong><br>` +
                `Difficulty: <strong>${category}</strong> (${score}%)<br>` +
                `<small>Based on your academic profile and course characteristics</small>`,
                'info'
            );
        } else {
            showAlert('Difficulty prediction not available for this course', 'warning');
        }
    }, function(error) {
        console.error('Error getting difficulty:', error);
        let errorMsg = 'Failed to get course difficulty. Please try again.';
        if (error && error.message) {
            errorMsg = error.message;
        }
        showAlert(errorMsg, 'danger');
    });
    
    if (btn) {
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }, 1500);
    }
}

function sendChatMessage() {
    const question = $('#chatInput').val().trim();
    if (!question) return;
    
    $('#chatContainer').append(`
        <div class="chat-message user">
            <strong>You:</strong> ${question}
        </div>
    `);
    $('#chatInput').val('');
    $('#chatContainer').scrollTop($('#chatContainer')[0].scrollHeight);
    
    const loadingId = 'loading-' + Date.now();
    $('#chatContainer').append(`
        <div class="chat-message bot" id="${loadingId}">
            <strong>Advisor:</strong> <span class="spinner-border spinner-border-sm"></span> Thinking...
        </div>
    `);
    $('#chatContainer').scrollTop($('#chatContainer')[0].scrollHeight);
    
    API.post('/api/advisor/chat', { question: question }, function(response) {
        $('#' + loadingId).remove();
        
        let advisorResponse = '';
        if (response && response.success !== false) {
            advisorResponse = response.response || response.message || 'I apologize, but I encountered an error. Please try again.';
        } else {
            advisorResponse = response.message || 'I apologize, but I encountered an error. Please try again.';
        }
        
        const escapedResponse = $('<div>').text(advisorResponse).html();
        $('#chatContainer').append(`
            <div class="chat-message bot">
                <strong>Advisor:</strong> ${escapedResponse}
            </div>
        `);
        $('#chatContainer').scrollTop($('#chatContainer')[0].scrollHeight);
    }, function(error) {
        $('#' + loadingId).remove();
        
        console.error('Chat error:', error);
        let errorMsg = 'I apologize, but I\'m having trouble responding right now. Please try again or rephrase your question.';
        if (error && error.responseJSON && error.responseJSON.message) {
            errorMsg = error.responseJSON.message;
        } else if (error && error.message) {
            errorMsg = error.message;
        }
        
        $('#chatContainer').append(`
            <div class="chat-message bot">
                <strong>Advisor:</strong> ${errorMsg}
            </div>
        `);
        $('#chatContainer').scrollTop($('#chatContainer')[0].scrollHeight);
    });
}

function editCourse(courseId, courseCode, courseName, currentGrade, currentSemester) {
    $('#editCourseId').val(courseId);
    $('#editCourseCode').text(courseCode);
    $('#editCourseName').text(courseName);
    $('#editCourseGrade').val(currentGrade);
    $('#editCourseSemester').val(currentSemester);
    
    const modal = new bootstrap.Modal(document.getElementById('editCourseModal'));
    modal.show();
}

function saveCourseEdit() {
    const saveBtn = document.querySelector('#editCourseModal .btn-primary');
    if (saveBtn.disabled) return;
    
    const courseId = $('#editCourseId').val();
    const grade = $('#editCourseGrade').val();
    const semester = parseInt($('#editCourseSemester').val());
    
    if (!courseId) {
        showAlert('Invalid course ID', 'danger');
        return;
    }
    
    if (!grade) {
        showAlert('Please select a grade', 'warning');
        return;
    }
    
    if (isNaN(semester) || semester < 1) {
        showAlert('Please enter a valid semester', 'warning');
        return;
    }
    
    const data = {
        grade: grade,
        semester_taken: semester
    };
    
    const originalText = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
    
    $.ajax({
        url: `/api/courses/completed/${courseId}`,
        method: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(response) {
            if (response.success) {
                const modal = bootstrap.Modal.getInstance(document.getElementById('editCourseModal'));
                if (modal) {
                    modal.hide();
                }
                loadCompletedCourses();
                loadProfile();
                loadUnlockedCourses();
                loadRecommendations();
                loadBottlenecks();
                loadAvailableCourses();
                showAlert('Course updated successfully!', 'success');
            } else {
                showAlert(response.message || 'Failed to update course', 'danger');
            }
        },
        error: function(xhr, status, error) {
            console.error('Error updating course:', error);
            showAlert('Failed to update course. Please try again.', 'danger');
        },
        complete: function() {
            saveBtn.disabled = false;
            saveBtn.innerHTML = originalText;
        }
    });
}

function loadAvailableCourses() {
    $('#availableCoursesList').html('<div class="text-center py-3"><div class="spinner-border spinner-border-sm" role="status"></div> <small class="d-block mt-2">Loading...</small></div>');

    API.get('/api/courses/available?limit=200', function(response) {
        const courses = response.courses || [];

        let html = '';
        if (courses.length === 0) {
            html = '<p class="text-muted">No available courses. Complete prerequisites first!</p>';
        } else {
            html = `<div class="mb-2"><strong>${courses.length} courses available</strong> <small class="text-muted">(with fast difficulty predictions)</small></div>`;

            courses.slice(0, 100).forEach(course => {
                const courseCode = course.course_code || 'N/A';
                if (courseCode === 'N/A') return;

                const difficulty = course.difficulty_score || 0.5;
                const diff = formatDifficulty(difficulty);
                const diffPercent = (difficulty * 100).toFixed(0);
                const isMajor = course.is_major_course !== false;
                const badge = isMajor ? '<span class="badge bg-primary ms-1">Major</span>' : '<span class="badge bg-secondary ms-1">Prereq</span>';

                const subject = course.subject || '';
                const isMath = subject.toUpperCase().includes('MATH');
                const subjectClass = isMath ? 'border-danger' : '';

                html += `
                    <div class="course-item mb-2 p-2 border rounded ${subjectClass}">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <strong>${courseCode}</strong>${badge}
                                ${isMath ? '<span class="badge bg-danger ms-1">Math</span>' : ''}
                                <br><small class="text-muted">${course.name || 'N/A'}</small>
                                <br><small class="text-muted">${course.credit_hours || 0} credits | Level ${course.course_level || 100} | ${subject}</small>
                            </div>
                            <div class="text-end ms-2">
                                <span class="difficulty-badge ${diff.class}">${diff.text}</span>
                                <br><small class="text-muted">${diffPercent}%</small>
                                <br>
                                <button class="btn btn-sm btn-outline-primary mt-1" onclick="getCourseDifficulty('${courseCode.replace(/'/g, "\\'")}', this)" title="Get detailed difficulty">
                                    <i class="bi bi-info-circle"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        $('#availableCoursesList').html(html);
    }, function(error) {
        console.error('Error loading available courses:', error);
        $('#availableCoursesList').html('<p class="text-danger">Error loading courses. Please refresh.</p>');
    });
}

function deleteCourse(courseId, courseCode) {
    if (!confirm(`Are you sure you want to remove "${courseCode}" from your completed courses?`)) {
        return;
    }
    
    const deleteBtn = event.target.closest('button');
    const originalText = deleteBtn.innerHTML;
    deleteBtn.disabled = true;
    deleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    
    $.ajax({
        url: `/api/courses/completed/${courseId}`,
        method: 'DELETE',
        success: function(response) {
            if (response.success) {
                loadCompletedCourses();
                loadProfile();
                loadUnlockedCourses();
                loadRecommendations();
                loadBottlenecks();
                loadAvailableCourses();
                showAlert('Course removed successfully!', 'success');
            } else {
                showAlert(response.message || 'Failed to remove course', 'danger');
            }
        },
        error: function(xhr, status, error) {
            console.error('Error deleting course:', error);
            showAlert('Failed to remove course. Please try again.', 'danger');
        },
        complete: function() {
            deleteBtn.disabled = false;
            deleteBtn.innerHTML = originalText;
        }
    });
}


function loadCalendarEvents() {
    const viewMode = $('#calendarViewMode').val() || 'list';
    const filterType = $('#calendarFilterType').val() || '';
    
    $('#calendarContainer').html('<div class="text-center py-4"><div class="spinner-border" role="status"></div> <p class="mt-2">Loading calendar...</p></div>');
    
    API.get('/api/calendar/events', function(response) {
        if (!response || response.success === false) {
            const errorMsg = response && response.message ? response.message : 'Error loading calendar events.';
            $('#calendarContainer').html(`<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> ${errorMsg}</div>`);
            return;
        }
        
        let events = response.events || [];
        
        if (filterType) {
            events = events.filter(e => e.event_type === filterType);
        }
        
        if (viewMode === 'list') {
            displayCalendarList(events);
        } else if (viewMode === 'month') {
            displayCalendarMonth(events);
        } else if (viewMode === 'week') {
            displayCalendarWeek(events);
        }
    }, function(error) {
        console.error('Calendar events error:', error);
        const errorMsg = error && error.message ? error.message : 'Failed to load calendar events. Please refresh the page.';
        $('#calendarContainer').html(`<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> ${errorMsg}</div>`);
    });
}

function displayCalendarList(events) {
    if (events.length === 0) {
        $('#calendarContainer').html('<div class="alert alert-info"><i class="bi bi-info-circle"></i> No calendar events. Click "Add Event" to create one.</div>');
        return;
    }
    
    events.sort((a, b) => new Date(a.start_date) - new Date(b.start_date));
    
    let html = '<div class="list-group">';
    events.forEach(event => {
        const startDate = new Date(event.start_date);
        const endDate = event.end_date ? new Date(event.end_date) : null;
        const isPast = startDate < new Date();
        const isCompleted = event.is_completed;
        
        html += `
            <div class="list-group-item ${isPast && !isCompleted ? 'list-group-item-warning' : ''} ${isCompleted ? 'list-group-item-success' : ''}">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center gap-2 mb-2">
                            <span class="badge" style="background-color: ${event.color}">${event.event_type}</span>
                            <h6 class="mb-0">${event.title}</h6>
                            ${isCompleted ? '<span class="badge bg-success">Completed</span>' : ''}
                        </div>
                        ${event.description ? `<p class="mb-2 text-muted">${event.description}</p>` : ''}
                        <small class="text-muted">
                            <i class="bi bi-calendar"></i> ${formatDate(startDate)}
                            ${endDate ? ` - ${formatDate(endDate)}` : ''}
                        </small>
                    </div>
                    <div class="ms-3">
                        <button class="btn btn-sm btn-outline-primary me-1" onclick="editCalendarEvent(${event.id})" title="Edit">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteCalendarEvent(${event.id})" title="Delete">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    $('#calendarContainer').html(html);
}

function displayCalendarMonth(events) {
    displayCalendarList(events);
}

function displayCalendarWeek(events) {
    displayCalendarList(events);
}

function showAddCalendarEventModal() {
    $('#calendarEventId').val('');
    $('#calendarEventTitle').val('');
    $('#calendarEventDescription').val('');
    $('#calendarEventType').val('other');
    $('#calendarEventStartDate').val('');
    $('#calendarEventEndDate').val('');
    $('#calendarEventAllDay').prop('checked', true);
    $('#calendarEventColor').val('#3b82f6');
    $('#calendarEventReminder').val(0);
    $('#calendarEventModalLabel').text('Add Calendar Event');
    
    const modal = new bootstrap.Modal(document.getElementById('calendarEventModal'));
    modal.show();
}

function editCalendarEvent(eventId) {
    API.get('/api/calendar/events', function(response) {
        if (!response.success) return;
        
        const event = response.events.find(e => e.id === eventId);
        if (!event) return;
        
        $('#calendarEventId').val(event.id);
        $('#calendarEventTitle').val(event.title);
        $('#calendarEventDescription').val(event.description || '');
        $('#calendarEventType').val(event.event_type);
        
        if (event.start_date) {
            const start = new Date(event.start_date);
            $('#calendarEventStartDate').val(start.toISOString().slice(0, 16));
        }
        if (event.end_date) {
            const end = new Date(event.end_date);
            $('#calendarEventEndDate').val(end.toISOString().slice(0, 16));
        }
        
        $('#calendarEventAllDay').prop('checked', event.is_all_day);
        $('#calendarEventColor').val(event.color);
        $('#calendarEventReminder').val(event.reminder_days);
        $('#calendarEventModalLabel').text('Edit Calendar Event');
        
        const modal = new bootstrap.Modal(document.getElementById('calendarEventModal'));
        modal.show();
    });
}

function saveCalendarEvent() {
    const btn = $('#calendarEventModal').find('button[onclick="saveCalendarEvent()"]');
    if (btn.prop('disabled')) return;
    
    const eventId = $('#calendarEventId').val();
    const data = {
        title: $('#calendarEventTitle').val(),
        description: $('#calendarEventDescription').val(),
        event_type: $('#calendarEventType').val(),
        start_date: $('#calendarEventStartDate').val(),
        end_date: $('#calendarEventEndDate').val() || null,
        is_all_day: $('#calendarEventAllDay').is(':checked'),
        color: $('#calendarEventColor').val(),
        reminder_days: parseInt($('#calendarEventReminder').val()) || 0
    };
    
    if (!data.title || !data.start_date) {
        showAlert('Please fill in required fields', 'warning');
        return;
    }
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    const url = eventId ? `/api/calendar/events/${eventId}` : '/api/calendar/events';
    const method = eventId ? 'PUT' : 'POST';
    
    API[method.toLowerCase()](url, data, function(response) {
        if (response.success) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('calendarEventModal'));
            if (modal) modal.hide();
            loadCalendarEvents();
            showAlert('Calendar event saved successfully!', 'success');
        } else {
            showAlert(response.message || 'Failed to save event', 'danger');
        }
        btn.prop('disabled', false).html(originalText);
    }, function() {
        showAlert('Failed to save calendar event', 'danger');
        btn.prop('disabled', false).html(originalText);
    });
}

function deleteCalendarEvent(eventId) {
    if (!confirm('Are you sure you want to delete this event?')) return;
    
    $.ajax({
        url: `/api/calendar/events/${eventId}`,
        method: 'DELETE',
        success: function(response) {
            if (response.success) {
                loadCalendarEvents();
                showAlert('Event deleted successfully!', 'success');
            } else {
                showAlert(response.message || 'Failed to delete event', 'danger');
            }
        },
        error: function() {
            showAlert('Failed to delete event', 'danger');
        }
    });
}

function formatDate(date) {
    return new Date(date).toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}


function loadFinancialSummary() {
    API.get('/api/financial/summary', function(response) {
        if (!response.success) return;
        
        const summary = response.summary;
        $('#financialTotalIncome').text('$' + summary.total_income.toFixed(2));
        $('#financialTotalExpenses').text('$' + summary.total_expenses.toFixed(2));
        $('#financialNetBalance').text('$' + summary.net_balance.toFixed(2));
        $('#financialNetBalance').removeClass('text-success text-danger').addClass(summary.net_balance >= 0 ? 'text-success' : 'text-danger');
        $('#financialUnpaid').text('$' + summary.unpaid_expenses.toFixed(2));
    });
}

function loadFinancialRecords() {
    const semester = $('#financialSemesterFilter').val() || '';
    
    $('#financialRecordsList').html('<div class="text-center py-3"><div class="spinner-border spinner-border-sm" role="status"></div> Loading...</div>');
    
    const url = semester ? `/api/financial/records?semester=${encodeURIComponent(semester)}` : '/api/financial/records';
    
    API.get(url, function(response) {
        if (!response.success) {
            $('#financialRecordsList').html('<div class="alert alert-danger">Error loading financial records.</div>');
            return;
        }
        
        const records = response.records || [];
        
        if (records.length === 0) {
            $('#financialRecordsList').html('<div class="alert alert-info"><i class="bi bi-info-circle"></i> No financial records. Click "Add Record" to create one.</div>');
            return;
        }
        
        let html = '<div class="table-responsive"><table class="table table-striped"><thead><tr><th>Type</th><th>Title</th><th>Amount</th><th>Semester</th><th>Due Date</th><th>Status</th><th>Actions</th></tr></thead><tbody>';
        
        records.forEach(record => {
            const amount = parseFloat(record.amount);
            const amountClass = amount >= 0 ? 'text-success' : 'text-danger';
            const amountSign = amount >= 0 ? '+' : '';
            
            html += `
                <tr>
                    <td><span class="badge bg-secondary">${record.record_type}</span></td>
                    <td>${record.title}</td>
                    <td class="${amountClass}"><strong>${amountSign}$${Math.abs(amount).toFixed(2)}</strong></td>
                    <td>${record.semester || '-'}</td>
                    <td>${record.due_date ? formatDate(record.due_date) : '-'}</td>
                    <td>${record.is_paid ? '<span class="badge bg-success">Paid</span>' : '<span class="badge bg-warning">Unpaid</span>'}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary me-1" onclick="editFinancialRecord(${record.id})" title="Edit">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteFinancialRecord(${record.id})" title="Delete">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        });
        
        html += '</tbody></table></div>';
        $('#financialRecordsList').html(html);
        
        loadFinancialSummary();
        loadBudgetPlanning();
    }, function() {
        $('#financialRecordsList').html('<div class="alert alert-danger">Failed to load financial records.</div>');
    });
}

function showAddFinancialRecordModal() {
    $('#financialRecordId').val('');
    $('#financialRecordType').val('expense');
    $('#financialRecordCategory').val('other');
    $('#financialRecordTitle').val('');
    $('#financialRecordDescription').val('');
    $('#financialRecordAmount').val('');
    $('#financialRecordSemester').val('');
    $('#financialRecordDueDate').val('');
    $('#financialRecordIsPaid').prop('checked', false);
    $('#financialRecordModalLabel').text('Add Financial Record');
    
    const modal = new bootstrap.Modal(document.getElementById('financialRecordModal'));
    modal.show();
}

function editFinancialRecord(recordId) {
    API.get('/api/financial/records', function(response) {
        if (!response.success) return;
        
        const record = response.records.find(r => r.id === recordId);
        if (!record) return;
        
        $('#financialRecordId').val(record.id);
        $('#financialRecordType').val(record.record_type);
        $('#financialRecordCategory').val(record.category || 'other');
        $('#financialRecordTitle').val(record.title);
        $('#financialRecordDescription').val(record.description || '');
        $('#financialRecordAmount').val(Math.abs(record.amount));
        $('#financialRecordSemester').val(record.semester || '');
        
        if (record.due_date) {
            const due = new Date(record.due_date);
            $('#financialRecordDueDate').val(due.toISOString().slice(0, 16));
        }
        
        $('#financialRecordIsPaid').prop('checked', record.is_paid);
        $('#financialRecordModalLabel').text('Edit Financial Record');
        
        const modal = new bootstrap.Modal(document.getElementById('financialRecordModal'));
        modal.show();
    });
}

function saveFinancialRecord() {
    const btn = $('#financialRecordModal').find('button[onclick="saveFinancialRecord()"]');
    if (btn.prop('disabled')) return;
    
    const recordId = $('#financialRecordId').val();
    const recordType = $('#financialRecordType').val();
    let amount = parseFloat($('#financialRecordAmount').val()) || 0;
    
    if (recordType === 'expense' || recordType === 'tuition' || recordType === 'course_fee') {
        amount = -Math.abs(amount);
    } else {
        amount = Math.abs(amount);
    }
    
    const data = {
        record_type: recordType,
        category: $('#financialRecordCategory').val(),
        title: $('#financialRecordTitle').val(),
        description: $('#financialRecordDescription').val(),
        amount: amount,
        semester: $('#financialRecordSemester').val() || null,
        due_date: $('#financialRecordDueDate').val() || null,
        is_paid: $('#financialRecordIsPaid').is(':checked')
    };
    
    if (!data.title || !data.amount) {
        showAlert('Please fill in required fields', 'warning');
        return;
    }
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    const url = recordId ? `/api/financial/records/${recordId}` : '/api/financial/records';
    const method = recordId ? 'PUT' : 'POST';
    
    API[method.toLowerCase()](url, data, function(response) {
        if (response.success) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('financialRecordModal'));
            if (modal) modal.hide();
            loadFinancialRecords();
            showAlert('Financial record saved successfully!', 'success');
        } else {
            showAlert(response.message || 'Failed to save record', 'danger');
        }
        btn.prop('disabled', false).html(originalText);
    }, function() {
        showAlert('Failed to save financial record', 'danger');
        btn.prop('disabled', false).html(originalText);
    });
}

function deleteFinancialRecord(recordId) {
    if (!confirm('Are you sure you want to delete this financial record?')) return;
    
    $.ajax({
        url: `/api/financial/records/${recordId}`,
        method: 'DELETE',
        success: function(response) {
            if (response.success) {
                loadFinancialRecords();
                showAlert('Record deleted successfully!', 'success');
            } else {
                showAlert(response.message || 'Failed to delete record', 'danger');
            }
        },
        error: function() {
            showAlert('Failed to delete record', 'danger');
        }
    });
}

function calculateTuition() {
    const data = {
        credits: parseFloat($('#tuitionCredits').val()) || 0,
        cost_per_credit: parseFloat($('#tuitionCostPerCredit').val()) || 500,
        fees: parseFloat($('#tuitionFees').val()) || 500,
        semester: $('#tuitionSemester').val() || 'Fall 2024',
        save_record: $('#tuitionSaveRecord').is(':checked')
    };
    
    if (!data.credits || !data.semester) {
        showAlert('Please fill in required fields', 'warning');
        return;
    }
    
    API.post('/api/financial/tuition-calculator', data, function(response) {
        if (!response.success) {
            showAlert(response.message || 'Failed to calculate tuition', 'danger');
            return;
        }
        
        const calc = response.calculation;
        const html = `
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">Tuition Calculation</h5>
                    <hr>
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>Credits:</strong> ${calc.credits}</p>
                            <p><strong>Cost per Credit:</strong> $${calc.cost_per_credit.toFixed(2)}</p>
                            <p><strong>Base Tuition:</strong> $${calc.base_tuition.toFixed(2)}</p>
                        </div>
                        <div class="col-md-6">
                            <p><strong>Fees:</strong> $${calc.fees.toFixed(2)}</p>
                            <p><strong>Semester:</strong> ${calc.semester}</p>
                            <h4 class="text-primary"><strong>Total: $${calc.total.toFixed(2)}</strong></h4>
                        </div>
                    </div>
                    ${data.save_record ? '<div class="alert alert-success mt-3"><i class="bi bi-check-circle"></i> Record saved to financial records.</div>' : ''}
                </div>
            </div>
        `;
        
        $('#tuitionCalculatorResult').html(html);
        if (data.save_record) {
            loadFinancialRecords();
        }
    }, function() {
        showAlert('Failed to calculate tuition', 'danger');
    });
}

function loadScholarships() {
    $('#scholarshipsList').html('<div class="text-center py-3"><div class="spinner-border spinner-border-sm" role="status"></div> Loading...</div>');
    
    API.get('/api/financial/scholarships', function(response) {
        if (!response.success) {
            $('#scholarshipsList').html('<div class="alert alert-danger">Error loading scholarships.</div>');
            return;
        }
        
        const scholarships = response.scholarships || [];
        
        if (scholarships.length === 0) {
            $('#scholarshipsList').html('<div class="alert alert-info"><i class="bi bi-info-circle"></i> No scholarships. Click "Add Scholarship" to create one.</div>');
            return;
        }
        
        let html = '';
        scholarships.forEach(scholarship => {
            const deadline = scholarship.application_deadline ? new Date(scholarship.application_deadline) : null;
            const isPastDeadline = deadline && deadline < new Date();
            
            html += `
                <div class="card mb-3 ${isPastDeadline && !scholarship.is_applied ? 'border-warning' : ''}">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <h5 class="card-title">${scholarship.name} <span class="badge bg-success">$${scholarship.amount.toFixed(2)}</span></h5>
                                ${scholarship.description ? `<p class="text-muted">${scholarship.description}</p>` : ''}
                                <div class="row g-2 mt-2">
                                    ${scholarship.eligibility_gpa_min ? `<div class="col-md-4"><small><strong>Min GPA:</strong> ${scholarship.eligibility_gpa_min.toFixed(2)}</small></div>` : ''}
                                    ${scholarship.eligibility_credits_min ? `<div class="col-md-4"><small><strong>Min Credits:</strong> ${scholarship.eligibility_credits_min}</small></div>` : ''}
                                    ${scholarship.eligibility_major ? `<div class="col-md-4"><small><strong>Major:</strong> ${scholarship.eligibility_major}</small></div>` : ''}
                                    ${deadline ? `<div class="col-md-4"><small><strong>Deadline:</strong> ${formatDate(deadline)} ${isPastDeadline ? '<span class="badge bg-danger">Past</span>' : ''}</small></div>` : ''}
                                </div>
                                <div class="mt-2">
                                    ${scholarship.is_applied ? '<span class="badge bg-info">Applied</span>' : ''}
                                    ${scholarship.is_awarded ? '<span class="badge bg-success">Awarded</span>' : ''}
                                    ${scholarship.renewal_required ? '<span class="badge bg-warning">Renewal Required</span>' : ''}
                                </div>
                            </div>
                            <div class="ms-3">
                                <button class="btn btn-sm btn-outline-primary me-1" onclick="editScholarship(${scholarship.id})" title="Edit">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger" onclick="deleteScholarship(${scholarship.id})" title="Delete">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        $('#scholarshipsList').html(html);
    }, function() {
        $('#scholarshipsList').html('<div class="alert alert-danger">Failed to load scholarships.</div>');
    });
}

function showAddScholarshipModal() {
    $('#scholarshipId').val('');
    $('#scholarshipName').val('');
    $('#scholarshipDescription').val('');
    $('#scholarshipAmount').val('');
    $('#scholarshipGpaMin').val('');
    $('#scholarshipCreditsMin').val('');
    $('#scholarshipMajor').val('');
    $('#scholarshipDeadline').val('');
    $('#scholarshipRenewal').prop('checked', false);
    $('#scholarshipRenewalGpa').val('');
    $('#scholarshipApplied').prop('checked', false);
    $('#scholarshipAwarded').prop('checked', false);
    $('#scholarshipModalLabel').text('Add Scholarship');
    
    const modal = new bootstrap.Modal(document.getElementById('scholarshipModal'));
    modal.show();
}

function editScholarship(scholarshipId) {
    API.get('/api/financial/scholarships', function(response) {
        if (!response.success) return;
        
        const scholarship = response.scholarships.find(s => s.id === scholarshipId);
        if (!scholarship) return;
        
        $('#scholarshipId').val(scholarship.id);
        $('#scholarshipName').val(scholarship.name);
        $('#scholarshipDescription').val(scholarship.description || '');
        $('#scholarshipAmount').val(scholarship.amount);
        $('#scholarshipGpaMin').val(scholarship.eligibility_gpa_min || '');
        $('#scholarshipCreditsMin').val(scholarship.eligibility_credits_min || '');
        $('#scholarshipMajor').val(scholarship.eligibility_major || '');
        
        if (scholarship.application_deadline) {
            const deadline = new Date(scholarship.application_deadline);
            $('#scholarshipDeadline').val(deadline.toISOString().slice(0, 16));
        }
        
        $('#scholarshipRenewal').prop('checked', scholarship.renewal_required);
        $('#scholarshipRenewalGpa').val(scholarship.renewal_gpa_min || '');
        $('#scholarshipApplied').prop('checked', scholarship.is_applied);
        $('#scholarshipAwarded').prop('checked', scholarship.is_awarded);
        $('#scholarshipModalLabel').text('Edit Scholarship');
        
        const modal = new bootstrap.Modal(document.getElementById('scholarshipModal'));
        modal.show();
    });
}

function saveScholarship() {
    const btn = $('#scholarshipModal').find('button[onclick="saveScholarship()"]');
    if (btn.prop('disabled')) return;
    
    const scholarshipId = $('#scholarshipId').val();
    const data = {
        name: $('#scholarshipName').val(),
        description: $('#scholarshipDescription').val(),
        amount: parseFloat($('#scholarshipAmount').val()) || 0,
        eligibility_gpa_min: $('#scholarshipGpaMin').val() || null,
        eligibility_credits_min: $('#scholarshipCreditsMin').val() || null,
        eligibility_major: $('#scholarshipMajor').val() || null,
        application_deadline: $('#scholarshipDeadline').val() || null,
        renewal_required: $('#scholarshipRenewal').is(':checked'),
        renewal_gpa_min: $('#scholarshipRenewalGpa').val() || null,
        is_applied: $('#scholarshipApplied').is(':checked'),
        is_awarded: $('#scholarshipAwarded').is(':checked')
    };
    
    if (!data.name || !data.amount) {
        showAlert('Please fill in required fields', 'warning');
        return;
    }
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    const url = scholarshipId ? `/api/financial/scholarships/${scholarshipId}` : '/api/financial/scholarships';
    const method = scholarshipId ? 'PUT' : 'POST';
    
    API[method.toLowerCase()](url, data, function(response) {
        if (response.success) {
            const modal = bootstrap.Modal.getInstance(document.getElementById('scholarshipModal'));
            if (modal) modal.hide();
            loadScholarships();
            showAlert('Scholarship saved successfully!', 'success');
        } else {
            showAlert(response.message || 'Failed to save scholarship', 'danger');
        }
        btn.prop('disabled', false).html(originalText);
    }, function() {
        showAlert('Failed to save scholarship', 'danger');
        btn.prop('disabled', false).html(originalText);
    });
}

function deleteScholarship(scholarshipId) {
    if (!confirm('Are you sure you want to delete this scholarship?')) return;
    
    $.ajax({
        url: `/api/financial/scholarships/${scholarshipId}`,
        method: 'DELETE',
        success: function(response) {
            if (response.success) {
                loadScholarships();
                showAlert('Scholarship deleted successfully!', 'success');
            } else {
                showAlert(response.message || 'Failed to delete scholarship', 'danger');
            }
        },
        error: function() {
            showAlert('Failed to delete scholarship', 'danger');
        }
    });
}

function checkScholarshipEligibility() {
    API.get('/api/financial/scholarships/check-eligibility', function(response) {
        if (!response.success) {
            showAlert('Failed to check eligibility', 'danger');
            return;
        }
        
        const eligibility = response.eligibility || [];
        let html = '<div class="alert alert-info"><h6>Scholarship Eligibility Check</h6><ul class="mb-0">';
        
        eligibility.forEach(item => {
            if (item.eligible) {
                html += `<li class="text-success"><strong>${item.scholarship_name}</strong>: Eligible ✓</li>`;
            } else {
                html += `<li class="text-danger"><strong>${item.scholarship_name}</strong>: Not Eligible - ${item.reasons.join(', ')}</li>`;
            }
        });
        
        html += '</ul></div>';
        $('#scholarshipsList').prepend(html);
    }, function() {
        showAlert('Failed to check eligibility', 'danger');
    });
}

function loadBudgetPlanning() {
    API.get('/api/financial/summary', function(response) {
        if (!response.success) return;
        
        const summary = response.summary;
        const categoryTotals = summary.category_totals || {};
        
        let incomeHtml = '<ul class="list-group">';
        let hasIncome = false;
        for (const [cat, totals] of Object.entries(categoryTotals)) {
            if (totals.income > 0) {
                hasIncome = true;
                incomeHtml += `<li class="list-group-item d-flex justify-content-between"><span>${cat}</span><span class="text-success">+$${totals.income.toFixed(2)}</span></li>`;
            }
        }
        if (!hasIncome) {
            incomeHtml += '<li class="list-group-item text-muted">No income recorded</li>';
        }
        incomeHtml += '</ul>';
        $('#incomeBreakdown').html(incomeHtml);
        
        let expenseHtml = '<ul class="list-group">';
        let hasExpenses = false;
        for (const [cat, totals] of Object.entries(categoryTotals)) {
            if (totals.expenses > 0) {
                hasExpenses = true;
                expenseHtml += `<li class="list-group-item d-flex justify-content-between"><span>${cat}</span><span class="text-danger">-$${totals.expenses.toFixed(2)}</span></li>`;
            }
        }
        if (!hasExpenses) {
            expenseHtml += '<li class="list-group-item text-muted">No expenses recorded</li>';
        }
        expenseHtml += '</ul>';
        $('#expenseBreakdown').html(expenseHtml);
    });
}

$('button[data-bs-target="#calendar"]').on('shown.bs.tab', function() {
    loadCalendarEvents();
});

$('button[data-bs-target="#financial"]').on('shown.bs.tab', function() {
    loadFinancialRecords();
    loadScholarships();
    loadFinancialSummary();
});

$('button[data-bs-target="#budgetPlanning"]').on('shown.bs.tab', function() {
    loadBudgetPlanning();
});

$('button[data-bs-target="#studyTime"]').on('shown.bs.tab', function() {
    loadStudySessions();
    loadStudyGoals();
    loadStudyAnalytics();
});

$('button[data-bs-target="#assignments"]').on('shown.bs.tab', function() {
    loadAssignments('all');
});

$('button[data-bs-target="#goals"]').on('shown.bs.tab', function() {
    loadAcademicGoals('all');
});

$('button[data-bs-target="#wishlist"]').on('shown.bs.tab', function() {
    loadWishlist();
});

$('button[data-bs-target="#notes"]').on('shown.bs.tab', function() {
    loadStudyNotes();
    loadCoursesForFilter('notesCourseFilter');
});

$('button[data-bs-target="#resources"]').on('shown.bs.tab', function() {
    loadLearningResources();
    loadCoursesForFilter('resourcesCourseFilter');
});

function loadCoursesForFilter(filterId) {
    API.get('/api/courses/completed', function(response) {
        if (response && response.success && response.courses) {
            const select = $('#' + filterId);
            select.empty();
            select.append('<option value="">All Courses</option>');
            if (response.courses.length > 0) {
                response.courses.forEach(course => {
                    const courseName = course.name || course.course_name || 'N/A';
                    select.append(`<option value="${course.course_id}">${course.course_code} - ${courseName}</option>`);
                });
            }
        }
    }, function(error) {
        console.error('Error loading courses for filter:', error);
    });
}

function loadStudySessions() {
    API.get('/api/study/sessions', function(response) {
        if (response && response.success) {
            const sessions = response.sessions || [];
            let html = '<h6 class="mb-3">Recent Study Sessions</h6>';
            if (sessions.length === 0) {
                html += '<p class="text-muted">No study sessions logged yet. Click "Log Study Session" to get started!</p>';
            } else {
                html += '<div class="table-responsive"><table class="table table-hover"><thead><tr><th>Date</th><th>Course</th><th>Duration</th><th>Notes</th><th>Actions</th></tr></thead><tbody>';
                sessions.slice(0, 20).forEach(session => {
                    const hours = Math.floor(session.duration_minutes / 60);
                    const minutes = session.duration_minutes % 60;
                    html += `<tr>
                        <td>${new Date(session.date).toLocaleDateString()}</td>
                        <td>${session.course_code || 'N/A'}</td>
                        <td>${hours}h ${minutes}m</td>
                        <td>${session.notes || '-'}</td>
                        <td><button class="btn btn-sm btn-danger" onclick="deleteStudySession(${session.id})"><i class="bi bi-trash"></i></button></td>
                    </tr>`;
                });
                html += '</tbody></table></div>';
            }
            $('#studySessionsList').html(html);
        } else {
            $('#studySessionsList').html('<p class="text-danger">Error loading study sessions. Please try again.</p>');
        }
    }, function(error) {
        $('#studySessionsList').html('<p class="text-danger">Error loading study sessions. Please try again.</p>');
    });
}

function showAddStudySessionModal() {
    $('#studySessionId').val('');
    $('#studySessionModalTitle').text('Log Study Session');
    loadCoursesForSelect('studySessionCourse');
    $('#studySessionDate').val(new Date().toISOString().slice(0, 16));
    $('#studySessionDuration').val('');
    $('#studySessionNotes').val('');
    new bootstrap.Modal(document.getElementById('studySessionModal')).show();
}

function saveStudySession() {
    const btn = $('#studySessionModal').find('button[onclick="saveStudySession()"]');
    if (btn.prop('disabled')) return;
    
    const data = {
        course_id: parseInt($('#studySessionCourse').val()),
        date: $('#studySessionDate').val(),
        duration_minutes: parseInt($('#studySessionDuration').val()),
        notes: $('#studySessionNotes').val()
    };
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    API.post('/api/study/sessions', data, function(response) {
        if (response && response.success) {
            showAlert('Study session logged successfully!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('studySessionModal')).hide();
            loadStudySessions();
            loadStudyAnalytics();
        }
        btn.prop('disabled', false).html(originalText);
    }, function(error) {
        btn.prop('disabled', false).html(originalText);
    });
}

function deleteStudySession(sessionId) {
    if (confirm('Delete this study session?')) {
        API.delete('/api/study/sessions/' + sessionId, function(response) {
            if (response && response.success) {
                showAlert('Study session deleted', 'success');
                loadStudySessions();
                loadStudyAnalytics();
            }
        });
    }
}

function loadStudyGoals() {
    API.get('/api/study/goals', function(response) {
        if (response && response.success) {
            const goals = response.goals || [];
            let html = '<h6 class="mb-3">Study Goals</h6>';
            if (goals.length === 0) {
                html += '<p class="text-muted">No study goals set. Click "Set Study Goal" to create one!</p>';
            } else {
                goals.forEach(goal => {
                    html += `<div class="card mb-2">
                        <div class="card-body">
                            <h6>${goal.course_code || 'All Courses'} - ${goal.goal_type}</h6>
                            <p>Target: ${goal.target_hours_per_week} hrs/week, ${goal.target_hours_total} hrs total</p>
                            <button class="btn btn-sm btn-danger" onclick="deleteStudyGoal(${goal.id})"><i class="bi bi-trash"></i></button>
                        </div>
                    </div>`;
                });
            }
            $('#studyGoalsList').html(html);
        }
    });
}

function showAddStudyGoalModal() {
    $('#studyGoalId').val('');
    $('#studyGoalModalTitle').text('Set Study Goal');
    loadCoursesForSelect('studyGoalCourse', true);
    $('#studyGoalType').val('weekly');
    $('#studyGoalHoursPerWeek').val('0');
    $('#studyGoalHoursTotal').val('0');
    new bootstrap.Modal(document.getElementById('studyGoalModal')).show();
}

function saveStudyGoal() {
    const btn = $('#studyGoalModal').find('button[onclick="saveStudyGoal()"]');
    if (btn.prop('disabled')) return;
    
    const data = {
        course_id: $('#studyGoalCourse').val() ? parseInt($('#studyGoalCourse').val()) : null,
        goal_type: $('#studyGoalType').val(),
        target_hours_per_week: parseFloat($('#studyGoalHoursPerWeek').val()),
        target_hours_total: parseFloat($('#studyGoalHoursTotal').val()),
        is_active: true
    };
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    API.post('/api/study/goals', data, function(response) {
        if (response && response.success) {
            showAlert('Study goal created!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('studyGoalModal')).hide();
            loadStudyGoals();
        }
        btn.prop('disabled', false).html(originalText);
    }, function(error) {
        btn.prop('disabled', false).html(originalText);
    });
}

function deleteStudyGoal(goalId) {
    if (confirm('Delete this study goal?')) {
        API.delete('/api/study/goals/' + goalId, function(response) {
            if (response && response.success) {
                showAlert('Study goal deleted', 'success');
                loadStudyGoals();
            }
        });
    }
}

function loadStudyAnalytics() {
    API.get('/api/study/analytics?days=30', function(response) {
        if (response && response.success) {
            const analytics = response.analytics;
            let html = '<h6 class="mb-3">Study Analytics (Last 30 Days)</h6>';
            html += `<div class="row mb-3">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h5>${analytics.total_hours.toFixed(1)}</h5>
                            <p class="mb-0">Total Hours</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h5>${analytics.total_sessions}</h5>
                            <p class="mb-0">Total Sessions</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h5>${(analytics.total_hours / analytics.days_tracked).toFixed(1)}</h5>
                            <p class="mb-0">Hours/Day</p>
                        </div>
                    </div>
                </div>
            </div>`;
            
            if (analytics.goal_progress && analytics.goal_progress.length > 0) {
                html += '<h6>Goal Progress</h6>';
                analytics.goal_progress.forEach(progress => {
                    html += `<div class="mb-2">
                        <strong>${progress.course_code || 'All'}:</strong> ${progress.actual_hours.toFixed(1)} / ${progress.target_hours_per_week} hrs/week
                        <div class="progress">
                            <div class="progress-bar" style="width: ${Math.min(100, progress.progress_percent)}%"></div>
                        </div>
                    </div>`;
                });
            }
            
            $('#studyAnalytics').html(html);
        }
    });
}

function loadAssignments(status) {
    const url = status === 'all' ? '/api/assignments' : `/api/assignments?status=${status}`;
    API.get(url, function(response) {
        if (response && response.success) {
            const assignments = response.assignments || [];
            let html = '';
            if (assignments.length === 0) {
                html = '<p class="text-muted">No assignments found. Click "Add Assignment" to get started!</p>';
            } else {
                html = '<div class="table-responsive"><table class="table table-hover"><thead><tr><th>Course</th><th>Title</th><th>Type</th><th>Due Date</th><th>Priority</th><th>Status</th><th>Actions</th></tr></thead><tbody>';
                assignments.forEach(assignment => {
                    const dueDate = new Date(assignment.due_date);
                    const isOverdue = dueDate < new Date() && assignment.status !== 'completed';
                    html += `<tr class="${isOverdue ? 'table-danger' : ''}">
                        <td>${assignment.course_code || 'N/A'}</td>
                        <td>${assignment.title}</td>
                        <td>${assignment.assignment_type}</td>
                        <td>${dueDate.toLocaleDateString()}</td>
                        <td><span class="badge bg-${assignment.priority === 'high' ? 'danger' : assignment.priority === 'medium' ? 'warning' : 'secondary'}">${assignment.priority}</span></td>
                        <td><span class="badge bg-${assignment.status === 'completed' ? 'success' : 'warning'}">${assignment.status}</span></td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="editAssignment(${assignment.id})"><i class="bi bi-pencil"></i></button>
                            <button class="btn btn-sm btn-danger" onclick="deleteAssignment(${assignment.id})"><i class="bi bi-trash"></i></button>
                        </td>
                    </tr>`;
                });
                html += '</tbody></table></div>';
            }
            $('#assignmentsList').html(html);
        } else {
            $('#assignmentsList').html('<p class="text-danger">Error loading assignments. Please try again.</p>');
        }
    }, function(error) {
        $('#assignmentsList').html('<p class="text-danger">Error loading assignments. Please try again.</p>');
    });
}

function showAddAssignmentModal() {
    $('#assignmentId').val('');
    $('#assignmentModalTitle').text('Add Assignment');
    loadCoursesForSelect('assignmentCourse');
    $('#assignmentTitle').val('');
    $('#assignmentDescription').val('');
    $('#assignmentType').val('assignment');
    $('#assignmentDueDate').val('');
    $('#assignmentPriority').val('medium');
    $('#assignmentEstimatedHours').val('');
    new bootstrap.Modal(document.getElementById('assignmentModal')).show();
}

function editAssignment(assignmentId) {
    API.get('/api/assignments', function(response) {
        if (response && response.success) {
            const assignment = response.assignments.find(a => a.id === assignmentId);
            if (assignment) {
                $('#assignmentId').val(assignment.id);
                $('#assignmentModalTitle').text('Edit Assignment');
                loadCoursesForSelect('assignmentCourse');
                $('#assignmentCourse').val(assignment.course_id);
                $('#assignmentTitle').val(assignment.title);
                $('#assignmentDescription').val(assignment.description || '');
                $('#assignmentType').val(assignment.assignment_type);
                $('#assignmentDueDate').val(assignment.due_date ? assignment.due_date.slice(0, 16) : '');
                $('#assignmentPriority').val(assignment.priority);
                $('#assignmentEstimatedHours').val(assignment.estimated_hours || '');
                new bootstrap.Modal(document.getElementById('assignmentModal')).show();
            }
        }
    });
}

function saveAssignment() {
    const btn = $('#assignmentModal').find('button[onclick="saveAssignment()"]');
    if (btn.prop('disabled')) return;
    
    const assignmentId = $('#assignmentId').val();
    const data = {
        course_id: parseInt($('#assignmentCourse').val()),
        title: $('#assignmentTitle').val(),
        description: $('#assignmentDescription').val(),
        assignment_type: $('#assignmentType').val(),
        due_date: $('#assignmentDueDate').val(),
        priority: $('#assignmentPriority').val(),
        estimated_hours: $('#assignmentEstimatedHours').val() ? parseFloat($('#assignmentEstimatedHours').val()) : null
    };
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    if (assignmentId) {
        API.put('/api/assignments/' + assignmentId, data, function(response) {
            if (response && response.success) {
                showAlert('Assignment updated!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('assignmentModal')).hide();
                loadAssignments('all');
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    } else {
        API.post('/api/assignments', data, function(response) {
            if (response && response.success) {
                showAlert('Assignment added!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('assignmentModal')).hide();
                loadAssignments('all');
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    }
}

function deleteAssignment(assignmentId) {
    if (confirm('Delete this assignment?')) {
        API.delete('/api/assignments/' + assignmentId, function(response) {
            if (response && response.success) {
                showAlert('Assignment deleted', 'success');
                loadAssignments('all');
            }
        });
    }
}

function loadAcademicGoals(filter) {
    const url = filter === 'all' ? '/api/goals' : `/api/goals?is_completed=${filter === 'completed'}`;
    API.get(url, function(response) {
        if (response && response.success) {
            const goals = response.goals || [];
            let html = '';
            if (goals.length === 0) {
                html = '<p class="text-muted">No goals set. Click "Set New Goal" to create one!</p>';
            } else {
                goals.forEach(goal => {
                    const progress = goal.progress_percent || 0;
                    html += `<div class="card mb-3">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <h6>${goal.title}</h6>
                                    <p class="text-muted mb-0">${goal.description || ''}</p>
                                </div>
                                <span class="badge bg-${goal.is_completed ? 'success' : 'primary'}">${goal.is_completed ? 'Completed' : 'Active'}</span>
                            </div>
                            <div class="mb-2">
                                <strong>Progress:</strong> ${goal.current_value} / ${goal.target_value} (${progress.toFixed(1)}%)
                                <div class="progress mt-1">
                                    <div class="progress-bar" style="width: ${Math.min(100, progress)}%"></div>
                                </div>
                            </div>
                            <div class="d-flex gap-2">
                                <button class="btn btn-sm btn-primary" onclick="editAcademicGoal(${goal.id})"><i class="bi bi-pencil"></i> Edit</button>
                                <button class="btn btn-sm btn-danger" onclick="deleteAcademicGoal(${goal.id})"><i class="bi bi-trash"></i></button>
                            </div>
                        </div>
                    </div>`;
                });
            }
            $('#academicGoalsList').html(html);
        } else {
            $('#academicGoalsList').html('<p class="text-danger">Error loading goals. Please try again.</p>');
        }
    }, function(error) {
        $('#academicGoalsList').html('<p class="text-danger">Error loading goals. Please try again.</p>');
    });
}

function showAddGoalModal() {
    $('#goalId').val('');
    $('#goalModalTitle').text('Set Academic Goal');
    $('#goalType').val('gpa');
    $('#goalTitle').val('');
    $('#goalDescription').val('');
    $('#goalTargetValue').val('');
    $('#goalCurrentValue').val('0');
    $('#goalTargetDate').val('');
    $('#goalSemester').val('');
    new bootstrap.Modal(document.getElementById('goalModal')).show();
}

function editAcademicGoal(goalId) {
    API.get('/api/goals', function(response) {
        if (response && response.success) {
            const goal = response.goals.find(g => g.id === goalId);
            if (goal) {
                $('#goalId').val(goal.id);
                $('#goalModalTitle').text('Edit Academic Goal');
                $('#goalType').val(goal.goal_type);
                $('#goalTitle').val(goal.title);
                $('#goalDescription').val(goal.description || '');
                $('#goalTargetValue').val(goal.target_value);
                $('#goalCurrentValue').val(goal.current_value);
                $('#goalTargetDate').val(goal.target_date ? goal.target_date.slice(0, 10) : '');
                $('#goalSemester').val(goal.semester || '');
                new bootstrap.Modal(document.getElementById('goalModal')).show();
            }
        }
    });
}

function saveAcademicGoal() {
    const btn = $('#goalModal').find('button[onclick="saveAcademicGoal()"]');
    if (btn.prop('disabled')) return;
    
    const goalId = $('#goalId').val();
    const data = {
        goal_type: $('#goalType').val(),
        title: $('#goalTitle').val(),
        description: $('#goalDescription').val(),
        target_value: parseFloat($('#goalTargetValue').val()),
        current_value: parseFloat($('#goalCurrentValue').val()),
        target_date: $('#goalTargetDate').val() || null,
        semester: $('#goalSemester').val() || ''
    };
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    if (goalId) {
        API.put('/api/goals/' + goalId, data, function(response) {
            if (response && response.success) {
                showAlert('Goal updated!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('goalModal')).hide();
                loadAcademicGoals('all');
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    } else {
        API.post('/api/goals', data, function(response) {
            if (response && response.success) {
                showAlert('Goal created!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('goalModal')).hide();
                loadAcademicGoals('all');
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    }
}

function deleteAcademicGoal(goalId) {
    if (confirm('Delete this goal?')) {
        API.delete('/api/goals/' + goalId, function(response) {
            if (response && response.success) {
                showAlert('Goal deleted', 'success');
                loadAcademicGoals('all');
            }
        });
    }
}

function loadWishlist() {
    API.get('/api/wishlist', function(response) {
        if (response && response.success) {
            const wishlist = response.wishlist || [];
            let html = '';
            if (wishlist.length === 0) {
                html = '<p class="text-muted">Your wishlist is empty. Click "Add Course to Wishlist" to get started!</p>';
            } else {
                html = '<div class="table-responsive"><table class="table table-hover"><thead><tr><th>Course</th><th>Priority</th><th>Target Semester</th><th>Status</th><th>Notes</th><th>Actions</th></tr></thead><tbody>';
                wishlist.forEach(item => {
                    html += `<tr>
                        <td><strong>${item.course_code}</strong><br><small>${item.course_name || ''}</small></td>
                        <td><span class="badge bg-${item.priority >= 3 ? 'danger' : item.priority >= 2 ? 'warning' : 'secondary'}">${item.priority === 3 ? 'High' : item.priority === 2 ? 'Medium' : 'Low'}</span></td>
                        <td>${item.target_semester || '-'}</td>
                        <td><span class="badge bg-${item.is_unlocked ? 'success' : 'secondary'}">${item.is_unlocked ? 'Unlocked' : 'Locked'}</span></td>
                        <td>${item.notes || '-'}</td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="editWishlistItem(${item.id})"><i class="bi bi-pencil"></i></button>
                            <button class="btn btn-sm btn-danger" onclick="deleteWishlistItem(${item.id})"><i class="bi bi-trash"></i></button>
                        </td>
                    </tr>`;
                });
                html += '</tbody></table></div>';
            }
            $('#wishlistList').html(html);
        } else {
            $('#wishlistList').html('<p class="text-danger">Error loading wishlist. Please try again.</p>');
        }
    }, function(error) {
        $('#wishlistList').html('<p class="text-danger">Error loading wishlist. Please try again.</p>');
    });
}

function showAddWishlistModal() {
    $('#wishlistId').val('');
    $('#wishlistModalTitle').text('Add to Wishlist');
    loadUnlockedCoursesForSelect('wishlistCourse');
    $('#wishlistPriority').val('3');
    $('#wishlistTargetSemester').val('');
    $('#wishlistNotes').val('');
    new bootstrap.Modal(document.getElementById('wishlistModal')).show();
}

function editWishlistItem(wishlistId) {
    API.get('/api/wishlist', function(response) {
        if (response && response.success) {
            const item = response.wishlist.find(w => w.id === wishlistId);
            if (item) {
                $('#wishlistId').val(item.id);
                $('#wishlistModalTitle').text('Edit Wishlist Item');
                loadUnlockedCoursesForSelect('wishlistCourse');
                $('#wishlistCourse').val(item.course_id);
                $('#wishlistPriority').val(item.priority);
                $('#wishlistTargetSemester').val(item.target_semester || '');
                $('#wishlistNotes').val(item.notes || '');
                new bootstrap.Modal(document.getElementById('wishlistModal')).show();
            }
        }
    });
}

function saveWishlistItem() {
    const btn = $('#wishlistModal').find('button[onclick="saveWishlistItem()"]');
    if (btn.prop('disabled')) return;
    
    const wishlistId = $('#wishlistId').val();
    const data = {
        course_id: parseInt($('#wishlistCourse').val()),
        priority: parseInt($('#wishlistPriority').val()),
        target_semester: $('#wishlistTargetSemester').val(),
        notes: $('#wishlistNotes').val()
    };
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    if (wishlistId) {
        API.put('/api/wishlist/' + wishlistId, data, function(response) {
            if (response && response.success) {
                showAlert('Wishlist item updated!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('wishlistModal')).hide();
                loadWishlist();
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    } else {
        API.post('/api/wishlist', data, function(response) {
            if (response && response.success) {
                showAlert('Course added to wishlist!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('wishlistModal')).hide();
                loadWishlist();
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    }
}

function deleteWishlistItem(wishlistId) {
    if (confirm('Remove from wishlist?')) {
        API.delete('/api/wishlist/' + wishlistId, function(response) {
            if (response && response.success) {
                showAlert('Removed from wishlist', 'success');
                loadWishlist();
            }
        });
    }
}

function loadStudyNotes() {
    const courseId = $('#notesCourseFilter').val();
    const url = courseId ? `/api/notes?course_id=${courseId}` : '/api/notes';
    API.get(url, function(response) {
        if (response && response.success) {
            const notes = response.notes || [];
            let html = '';
            if (notes.length === 0) {
                html = '<p class="text-muted">No notes yet. Click "Create Note" to get started!</p>';
            } else {
                notes.forEach(note => {
                    html += `<div class="card mb-3">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <h6>${note.title}</h6>
                                    <p class="text-muted mb-1"><small>${note.course_code} ${note.topic ? '• ' + note.topic : ''}</small></p>
                                </div>
                                <div>
                                    <button class="btn btn-sm btn-primary" onclick="editStudyNote(${note.id})"><i class="bi bi-pencil"></i></button>
                                    <button class="btn btn-sm btn-danger" onclick="deleteStudyNote(${note.id})"><i class="bi bi-trash"></i></button>
                                </div>
                            </div>
                            <p>${note.content.substring(0, 200)}${note.content.length > 200 ? '...' : ''}</p>
                            ${note.tags ? `<div><small class="text-muted">Tags: ${note.tags}</small></div>` : ''}
                        </div>
                    </div>`;
                });
            }
            $('#studyNotesList').html(html);
        } else {
            $('#studyNotesList').html('<p class="text-danger">Error loading notes. Please try again.</p>');
        }
    }, function(error) {
        $('#studyNotesList').html('<p class="text-danger">Error loading notes. Please try again.</p>');
    });
}

function showAddNoteModal() {
    $('#noteId').val('');
    $('#noteModalTitle').text('Create Study Note');
    loadCoursesForSelect('noteCourse');
    $('#noteTitle').val('');
    $('#noteContent').val('');
    $('#noteTopic').val('');
    $('#noteTags').val('');
    new bootstrap.Modal(document.getElementById('noteModal')).show();
}

function editStudyNote(noteId) {
    API.get('/api/notes', function(response) {
        if (response && response.success) {
            const note = response.notes.find(n => n.id === noteId);
            if (note) {
                $('#noteId').val(note.id);
                $('#noteModalTitle').text('Edit Study Note');
                loadCoursesForSelect('noteCourse');
                $('#noteCourse').val(note.course_id);
                $('#noteTitle').val(note.title);
                $('#noteContent').val(note.content);
                $('#noteTopic').val(note.topic || '');
                $('#noteTags').val(note.tags || '');
                new bootstrap.Modal(document.getElementById('noteModal')).show();
            }
        }
    });
}

function saveStudyNote() {
    const btn = $('#noteModal').find('button[onclick="saveStudyNote()"]');
    if (btn.prop('disabled')) return;
    
    const noteId = $('#noteId').val();
    const data = {
        course_id: parseInt($('#noteCourse').val()),
        title: $('#noteTitle').val(),
        content: $('#noteContent').val(),
        topic: $('#noteTopic').val(),
        tags: $('#noteTags').val()
    };
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    if (noteId) {
        API.put('/api/notes/' + noteId, data, function(response) {
            if (response && response.success) {
                showAlert('Note updated!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('noteModal')).hide();
                loadStudyNotes();
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    } else {
        API.post('/api/notes', data, function(response) {
            if (response && response.success) {
                showAlert('Note created!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('noteModal')).hide();
                loadStudyNotes();
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    }
}

function deleteStudyNote(noteId) {
    if (confirm('Delete this note?')) {
        API.delete('/api/notes/' + noteId, function(response) {
            if (response && response.success) {
                showAlert('Note deleted', 'success');
                loadStudyNotes();
            }
        });
    }
}

function loadLearningResources() {
    const courseId = $('#resourcesCourseFilter').val();
    const resourceType = $('#resourcesTypeFilter').val();
    let url = '/api/resources';
    const params = [];
    if (courseId) params.push(`course_id=${courseId}`);
    if (resourceType) params.push(`resource_type=${resourceType}`);
    if (params.length > 0) url += '?' + params.join('&');
    
    API.get(url, function(response) {
        if (response && response.success) {
            const resources = response.resources || [];
            let html = '';
            if (resources.length === 0) {
                html = '<p class="text-muted">No resources saved. Click "Add Resource" to get started!</p>';
            } else {
                resources.forEach(resource => {
                    html += `<div class="card mb-3">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <h6><a href="${resource.url}" target="_blank">${resource.title}</a></h6>
                                    <p class="text-muted mb-1"><small>${resource.course_code} • ${resource.resource_type} ${resource.topic ? '• ' + resource.topic : ''}</small></p>
                                </div>
                                <div>
                                    <button class="btn btn-sm btn-success" onclick="markResourceHelpful(${resource.id})"><i class="bi bi-hand-thumbs-up"></i> ${resource.helpful_count || 0}</button>
                                    <button class="btn btn-sm btn-primary" onclick="editLearningResource(${resource.id})"><i class="bi bi-pencil"></i></button>
                                    <button class="btn btn-sm btn-danger" onclick="deleteLearningResource(${resource.id})"><i class="bi bi-trash"></i></button>
                                </div>
                            </div>
                            <p>${resource.description || ''}</p>
                            ${resource.tags ? `<div><small class="text-muted">Tags: ${resource.tags}</small></div>` : ''}
                        </div>
                    </div>`;
                });
            }
            $('#learningResourcesList').html(html);
        } else {
            $('#learningResourcesList').html('<p class="text-danger">Error loading resources. Please try again.</p>');
        }
    }, function(error) {
        $('#learningResourcesList').html('<p class="text-danger">Error loading resources. Please try again.</p>');
    });
}

function showAddResourceModal() {
    $('#resourceId').val('');
    $('#resourceModalTitle').text('Add Learning Resource');
    loadCoursesForSelect('resourceCourse');
    $('#resourceTitle').val('');
    $('#resourceType').val('link');
    $('#resourceUrl').val('');
    $('#resourceDescription').val('');
    $('#resourceTopic').val('');
    $('#resourceTags').val('');
    new bootstrap.Modal(document.getElementById('resourceModal')).show();
}

function editLearningResource(resourceId) {
    API.get('/api/resources', function(response) {
        if (response && response.success) {
            const resource = response.resources.find(r => r.id === resourceId);
            if (resource) {
                $('#resourceId').val(resource.id);
                $('#resourceModalTitle').text('Edit Learning Resource');
                loadCoursesForSelect('resourceCourse');
                $('#resourceCourse').val(resource.course_id);
                $('#resourceTitle').val(resource.title);
                $('#resourceType').val(resource.resource_type);
                $('#resourceUrl').val(resource.url);
                $('#resourceDescription').val(resource.description || '');
                $('#resourceTopic').val(resource.topic || '');
                $('#resourceTags').val(resource.tags || '');
                new bootstrap.Modal(document.getElementById('resourceModal')).show();
            }
        }
    });
}

function saveLearningResource() {
    const btn = $('#resourceModal').find('button[onclick="saveLearningResource()"]');
    if (btn.prop('disabled')) return;
    
    const resourceId = $('#resourceId').val();
    const data = {
        course_id: parseInt($('#resourceCourse').val()),
        title: $('#resourceTitle').val(),
        resource_type: $('#resourceType').val(),
        url: $('#resourceUrl').val(),
        description: $('#resourceDescription').val(),
        topic: $('#resourceTopic').val(),
        tags: $('#resourceTags').val()
    };
    
    const originalText = btn.html();
    btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');
    
    if (resourceId) {
        API.put('/api/resources/' + resourceId, data, function(response) {
            if (response && response.success) {
                showAlert('Resource updated!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('resourceModal')).hide();
                loadLearningResources();
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    } else {
        API.post('/api/resources', data, function(response) {
            if (response && response.success) {
                showAlert('Resource added!', 'success');
                bootstrap.Modal.getInstance(document.getElementById('resourceModal')).hide();
                loadLearningResources();
            }
            btn.prop('disabled', false).html(originalText);
        }, function(error) {
            btn.prop('disabled', false).html(originalText);
        });
    }
}

function deleteLearningResource(resourceId) {
    if (confirm('Delete this resource?')) {
        API.delete('/api/resources/' + resourceId, function(response) {
            if (response && response.success) {
                showAlert('Resource deleted', 'success');
                loadLearningResources();
            }
        });
    }
}

function markResourceHelpful(resourceId) {
    API.post('/api/resources/' + resourceId + '/helpful', {}, function(response) {
        if (response && response.success) {
            loadLearningResources();
        }
    });
}

function loadCoursesForSelect(selectId, includeAll = false) {
    API.get('/api/courses/completed', function(response) {
        if (response && response.success && response.courses) {
            const select = $('#' + selectId);
            select.empty();
            if (includeAll) {
                select.append('<option value="">All Courses</option>');
            }
            if (response.courses.length === 0) {
                select.append('<option value="">No completed courses</option>');
            } else {
                response.courses.forEach(course => {
                    const courseName = course.name || course.course_name || 'N/A';
                    select.append(`<option value="${course.course_id}">${course.course_code} - ${courseName}</option>`);
                });
            }
        } else {
            const select = $('#' + selectId);
            select.empty();
            select.append('<option value="">Error loading courses</option>');
        }
    }, function(error) {
        const select = $('#' + selectId);
        select.empty();
        select.append('<option value="">Error loading courses</option>');
    });
}

function loadUnlockedCoursesForSelect(selectId) {
    API.get('/api/courses/unlocked', function(response) {
        if (response && response.success && response.courses) {
            const select = $('#' + selectId);
            select.empty();
            select.append('<option value="">Select Course</option>');
            if (response.courses.length === 0) {
                select.append('<option value="">No unlocked courses</option>');
            } else {
                response.courses.forEach(course => {
                    const courseName = course.name || course.course_name || 'N/A';
                    const courseId = course.course_id || course.id;
                    select.append(`<option value="${courseId}">${course.course_code} - ${courseName}</option>`);
                });
            }
        } else {
            const select = $('#' + selectId);
            select.empty();
            select.append('<option value="">Error loading courses</option>');
        }
    }, function(error) {
        const select = $('#' + selectId);
        select.empty();
        select.append('<option value="">Error loading courses</option>');
    });
}
let performanceCharts = {};

function loadPerformanceDashboard() {
    API.get('/api/performance/dashboard', function(response) {
        if (response && response.success) {
            const data = response.data;
            
            $('#performanceGPA').text(data.current_gpa.toFixed(2));
            $('#performanceCourses').text(data.total_courses);
            $('#performanceCredits').text(data.total_credits);
            $('#performanceProgress').text(data.degree_progress.percentage + '%');
            
            renderGPATrendChart(data.gpa_trend);
            renderCoursePerformanceChart(data.course_performance);
            renderStudyTimeChart(data.study_analytics.by_date);
            renderStudyByCourseChart(data.study_analytics.by_course);
            renderAssignmentStats(data.assignment_stats);
            renderGoalsProgress(data.goal_stats);
            renderCoursePerformanceTable(data.course_performance);
        } else {
            showAlert('Failed to load performance data.', 'danger');
        }
    }, function(error) {
        showAlert('Failed to load performance data.', 'danger');
    });
}

function renderGPATrendChart(gpaTrend) {
    const ctx = document.getElementById('gpaTrendChart');
    if (!ctx) return;
    
    if (performanceCharts.gpaTrend) {
        performanceCharts.gpaTrend.destroy();
    }
    
    const labels = gpaTrend.map(item => item.month);
    const gpaData = gpaTrend.map(item => item.gpa);
    
    performanceCharts.gpaTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'GPA',
                data: gpaData,
                borderColor: 'rgb(99, 102, 241)',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    min: 0,
                    max: 4.0
                }
            }
        }
    });
}

function renderCoursePerformanceChart(coursePerformance) {
    const ctx = document.getElementById('coursePerformanceChart');
    if (!ctx) return;
    
    if (performanceCharts.coursePerformance) {
        performanceCharts.coursePerformance.destroy();
    }
    
    const recentCourses = coursePerformance.slice(0, 10);
    const labels = recentCourses.map(c => c.course_code);
    const gradePoints = recentCourses.map(c => c.grade_points);
    const predicted = recentCourses.map(c => c.predicted_difficulty || 0);
    
    performanceCharts.coursePerformance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Grade Points',
                data: gradePoints,
                backgroundColor: 'rgba(16, 185, 129, 0.6)',
                borderColor: 'rgb(16, 185, 129)',
                borderWidth: 1
            }, {
                label: 'Predicted Difficulty',
                data: predicted,
                type: 'line',
                borderColor: 'rgb(239, 68, 68)',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 4.0
                }
            }
        }
    });
}

function renderStudyTimeChart(studyByDate) {
    const ctx = document.getElementById('studyTimeChart');
    if (!ctx) return;
    
    if (performanceCharts.studyTime) {
        performanceCharts.studyTime.destroy();
    }
    
    const labels = studyByDate.map(item => item.date);
    const hours = studyByDate.map(item => item.hours);
    
    performanceCharts.studyTime = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Study Hours',
                data: hours,
                borderColor: 'rgb(245, 158, 11)',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function renderStudyByCourseChart(studyByCourse) {
    const ctx = document.getElementById('studyByCourseChart');
    if (!ctx) return;
    
    if (performanceCharts.studyByCourse) {
        performanceCharts.studyByCourse.destroy();
    }
    
    if (studyByCourse.length === 0) {
        ctx.getContext('2d').clearRect(0, 0, ctx.width, ctx.height);
        return;
    }
    
    const labels = studyByCourse.map(item => item.course_code);
    const hours = studyByCourse.map(item => item.total_hours);
    
    performanceCharts.studyByCourse = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: hours,
                backgroundColor: [
                    'rgba(99, 102, 241, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(239, 68, 68, 0.8)',
                    'rgba(139, 92, 246, 0.8)',
                    'rgba(6, 182, 212, 0.8)'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true
        }
    });
}

function renderAssignmentStats(stats) {
    let html = '<div class="row g-3">';
    html += '<div class="col-6"><div class="text-center p-3 bg-light rounded"><h3 class="mb-0">' + stats.total + '</h3><p class="mb-0 text-muted">Total</p></div></div>';
    html += '<div class="col-6"><div class="text-center p-3 bg-success bg-opacity-10 rounded"><h3 class="mb-0 text-success">' + stats.completed + '</h3><p class="mb-0 text-muted">Completed</p></div></div>';
    html += '<div class="col-6"><div class="text-center p-3 bg-warning bg-opacity-10 rounded"><h3 class="mb-0 text-warning">' + stats.pending + '</h3><p class="mb-0 text-muted">Pending</p></div></div>';
    html += '<div class="col-6"><div class="text-center p-3 bg-danger bg-opacity-10 rounded"><h3 class="mb-0 text-danger">' + stats.overdue + '</h3><p class="mb-0 text-muted">Overdue</p></div></div>';
    html += '</div>';
    
    $('#assignmentStatsContainer').html(html);
}

function renderGoalsProgress(goalStats) {
    let html = '<div class="mb-3">';
    html += '<p class="mb-2"><strong>Total Goals:</strong> ' + goalStats.total + '</p>';
    html += '<p class="mb-2"><strong>Completed:</strong> <span class="text-success">' + goalStats.completed + '</span></p>';
    html += '<p class="mb-3"><strong>In Progress:</strong> <span class="text-primary">' + goalStats.in_progress + '</span></p>';
    html += '</div>';
    
    if (goalStats.goals && goalStats.goals.length > 0) {
        goalStats.goals.forEach(function(goal) {
            html += '<div class="mb-3"><div class="d-flex justify-content-between mb-1"><span><strong>' + goal.title + '</strong></span><span>' + goal.progress + '%</span></div>';
            html += '<div class="progress" style="height: 20px;"><div class="progress-bar ' + (goal.is_completed ? 'bg-success' : 'bg-primary') + '" style="width: ' + goal.progress + '%"></div></div>';
            html += '<small class="text-muted">' + goal.current + ' / ' + goal.target + ' ' + goal.type + '</small></div>';
        });
    } else {
        html += '<p class="text-muted text-center">No goals set yet.</p>';
    }
    
    $('#goalsProgressContainer').html(html);
}

function renderCoursePerformanceTable(coursePerformance) {
    let html = '';
    if (coursePerformance.length === 0) {
        html = '<tr><td colspan="5" class="text-center text-muted">No course data available.</td></tr>';
    } else {
        coursePerformance.slice(0, 10).forEach(function(course) {
            html += '<tr><td><strong>' + course.course_code + '</strong><br><small class="text-muted">' + course.course_name + '</small></td>';
            html += '<td><span class="badge bg-primary">' + course.grade + '</span></td>';
            html += '<td>' + course.grade_points.toFixed(2) + '</td>';
            html += '<td>' + (course.predicted_difficulty ? course.predicted_difficulty.toFixed(2) : 'N/A') + '</td>';
            html += '<td>' + course.credits + '</td></tr>';
        });
    }
    $('#coursePerformanceTable').html(html);
}

function loadAIInsights() {
    loadAcademicRisk();
    loadPathInsights();
    loadSemesterTimeline();
}

function renderSemesterTimelineHTML(semesters) {
    if (!semesters || !semesters.length) {
        return '<p class="text-muted mb-0">No completed courses yet. Add courses under <strong>My Courses</strong> and set the <strong>semester</strong> for each.</p>';
    }
    let html = '<div class="d-flex flex-row flex-nowrap gap-3 pb-2 academic-journey-scroll" style="overflow-x: auto; scroll-snap-type: x mandatory;">';
    semesters.forEach(function(block) {
        const sem = block.semester;
        const courses = block.courses || [];
        html += '<div class="flex-shrink-0 rounded-3 shadow-sm border border-2 border-primary p-3 bg-white" style="min-width: 260px; max-width: 320px; scroll-snap-align: start; --bs-border-opacity: .35;">';
        html += '<div class="d-flex align-items-center justify-content-between mb-2 pb-2 border-bottom">';
        html += '<span class="fs-5 fw-bold text-primary">Semester ' + sem + '</span>';
        html += '<span class="badge bg-primary">' + (block.total_credits != null ? Number(block.total_credits).toFixed(1) : '0') + ' cr</span></div>';
        html += '<ul class="list-unstyled small mb-0">';
        courses.forEach(function(c) {
            const nm = (c.name || '');
            html += '<li class="mb-2 pb-2 border-bottom border-light"><div class="fw-semibold">' + (c.course_code || '') + '</div>';
            html += '<div class="text-muted" style="font-size: 0.8rem;">' + (nm.length > 48 ? nm.substring(0, 48) + '…' : nm) + '</div>';
            html += '<div><span class="badge bg-light text-dark border">' + (c.grade || '—') + '</span> <span class="text-muted">' + (c.credit_hours != null ? c.credit_hours : '') + ' cr</span></div></li>';
        });
        html += '</ul></div>';
    });
    html += '</div>';
    return html;
}

function loadAcademicJourneySection() {
    const el = $('#academicJourneySection');
    if (!el.length) return;
    el.html('<div class="text-center py-2"><div class="spinner-border spinner-border-sm"></div> <small class="text-muted">Loading journey…</small></div>');
    API.get('/api/student/semester-timeline', function(response) {
        if (!response || !response.success || !response.data) {
            el.html('<p class="text-muted">No timeline data.</p>');
            return;
        }
        const semesters = response.data.semesters || [];
        el.html(renderSemesterTimelineHTML(semesters));
    }, function() {
        el.html('<p class="text-danger small">Could not load academic journey.</p>');
    });
}

function loadPathInsights() {
    $('#pathInsightsCard').html('<div class="text-center py-2"><div class="spinner-border spinner-border-sm"></div> Loading…</div>');
    API.get('/api/student/insights', function(response) {
        if (!response || !response.success || !response.data) {
            $('#pathInsightsCard').html('<p class="text-muted">No insights available.</p>');
            return;
        }
        const d = response.data;
        let html = '';

        if (d.stats) {
            html += '<div class="alert alert-light border mb-3 small"><strong>Your record:</strong> ';
            html += (d.stats.total_credits_completed != null ? d.stats.total_credits_completed + ' credits' : '—');
            html += ' across <strong>' + (d.stats.semesters_recorded || 0) + '</strong> semester(s)';
            if (d.stats.avg_credits_per_semester > 0) {
                html += ' · ~' + d.stats.avg_credits_per_semester + ' cr/semester avg';
            }
            html += ' · GPA <strong>' + (d.gpa != null ? Number(d.gpa).toFixed(2) : '—') + '</strong></div>';
        }

        if (d.warnings && d.warnings.length) {
            html += '<h6 class="text-danger"><i class="bi bi-exclamation-octagon me-1"></i> Warnings</h6><ul class="small mb-3">';
            d.warnings.forEach(function(w) { html += '<li>' + w + '</li>'; });
            html += '</ul>';
        }

        if (d.recommendation_preview && d.recommendation_preview.length) {
            html += '<h6 class="text-success"><i class="bi bi-lightbulb me-1"></i> Suggested next courses (app recommendations)</h6><ul class="small mb-3">';
            d.recommendation_preview.slice(0, 6).forEach(function(x) {
                html += '<li><strong>' + (x.course_code || '') + '</strong> — ' + (x.name || '') + ' <span class="text-muted">(' + (x.difficulty_category || '') + ')</span></li>';
            });
            html += '</ul>';
        }

        if (d.suggestions && d.suggestions.length) {
            html += '<h6 class="text-primary">Path suggestions</h6><ul class="small mb-3">';
            d.suggestions.forEach(function(s) { html += '<li>' + s + '</li>'; });
            html += '</ul>';
        }

        if (d.prerequisite_risks && d.prerequisite_risks.length) {
            html += '<h6 class="mt-2">Prerequisite complexity</h6><p class="small text-muted mb-1">Courses with several missing prerequisites (plan early):</p><ul class="small mb-3">';
            d.prerequisite_risks.slice(0, 6).forEach(function(x) {
                html += '<li><strong>' + (x.course_code || '') + '</strong>: need ' + (x.missing_prerequisites || []).join(', ') + '</li>';
            });
            html += '</ul>';
        }

        if (d.delayed_foundations && d.delayed_foundations.length) {
            html += '<h6 class="mt-2">Major courses not yet taken</h6><p class="small text-muted mb-1">Intro / mid-level ' + (d.major || '') + ' courses still open (consider scheduling):</p><ul class="small mb-3">';
            d.delayed_foundations.slice(0, 8).forEach(function(x) {
                html += '<li><strong>' + (x.course_code || '') + '</strong> (level ' + (x.course_level || '') + ') — ' + (x.name || '') + '</li>';
            });
            html += '</ul>';
        }

        if (d.locked_high_impact && d.locked_high_impact.length) {
            html += '<h6 class="mt-2">High-impact locked courses</h6><p class="small text-muted mb-1">Unlock many later courses once prerequisites are met.</p><ul class="small mb-3">';
            d.locked_high_impact.slice(0, 8).forEach(function(x) {
                html += '<li><strong>' + (x.course_code || '') + '</strong> — ~' + (x.unlocks_count || 0) + ' unlocks. Missing: ' + (x.missing_prerequisites || []).join(', ') + '</li>';
            });
            html += '</ul>';
        }
        if (d.advanced_locked && d.advanced_locked.length) {
            html += '<h6 class="mt-3">300+ level still locked</h6><ul class="small mb-3">';
            d.advanced_locked.slice(0, 6).forEach(function(x) {
                html += '<li>' + (x.course_code || '') + ' (level ' + (x.course_level || '') + '): need ' + (x.missing_prerequisites || []).join(', ') + '</li>';
            });
            html += '</ul>';
        }
        if (d.next_semester_candidates && d.next_semester_candidates.length) {
            html += '<h6 class="mt-3">Strong options by unlock impact</h6><ul class="small mb-3">';
            d.next_semester_candidates.slice(0, 8).forEach(function(x) {
                html += '<li>' + (x.course_code || '') + ' — ' + (x.name || '') + ' (' + (x.credit_hours || 3) + ' cr, unlocks ~' + (x.unlocks_count || 0) + ')</li>';
            });
            html += '</ul>';
        }
        if (!html) {
            html = '<p class="text-muted mb-0">Complete more courses to see path insights.</p>';
        }
        $('#pathInsightsCard').html(html);
    }, function() {
        $('#pathInsightsCard').html('<p class="text-danger small">Could not load path insights.</p>');
    });
}

function loadSemesterTimeline() {
    $('#semesterTimelineCard').html('<div class="text-center py-2"><div class="spinner-border spinner-border-sm"></div> Loading…</div>');
    API.get('/api/student/semester-timeline', function(response) {
        if (!response || !response.success || !response.data) {
            $('#semesterTimelineCard').html('<p class="text-muted">No timeline data.</p>');
            return;
        }
        const semesters = response.data.semesters || [];
        $('#semesterTimelineCard').html(renderSemesterTimelineHTML(semesters));
    }, function() {
        $('#semesterTimelineCard').html('<p class="text-danger small">Could not load timeline.</p>');
    });
}

function loadAcademicRisk() {
    API.get('/api/student/academic-risk', function(response) {
        if (response && response.success && response.data) {
            const data = response.data;
            const riskScore = (data.risk_score * 100).toFixed(1);
            const riskCategory = data.risk_category || 'Unknown';
            
            let riskColor = 'success';
            let riskIcon = 'check-circle';
            if (riskCategory === 'Critical') {
                riskColor = 'danger';
                riskIcon = 'exclamation-triangle-fill';
            } else if (riskCategory === 'High') {
                riskColor = 'warning';
                riskIcon = 'exclamation-triangle';
            } else if (riskCategory === 'Medium') {
                riskColor = 'info';
                riskIcon = 'info-circle';
            }
            
            let riskFactorsHtml = '';
            if (data.risk_factors && data.risk_factors.length > 0) {
                riskFactorsHtml = '<div class="mt-3"><strong>Risk Factors:</strong><ul class="mb-0 mt-2">';
                data.risk_factors.forEach(factor => {
                    riskFactorsHtml += `<li>${factor}</li>`;
                });
                riskFactorsHtml += '</ul></div>';
            }
            
            let recommendationsHtml = '';
            if (data.recommendations && data.recommendations.length > 0) {
                recommendationsHtml = '<div class="mt-3"><strong>Recommendations:</strong><ul class="mb-0 mt-2">';
                data.recommendations.forEach(rec => {
                    recommendationsHtml += `<li>${rec}</li>`;
                });
                recommendationsHtml += '</ul></div>';
            }
            
            $('#academicRiskCard').html(`
                <div class="text-center mb-3">
                    <h3 class="text-${riskColor}"><i class="bi bi-${riskIcon}"></i> ${riskCategory} Risk</h3>
                    <div class="progress" style="height: 25px;">
                        <div class="progress-bar bg-${riskColor}" role="progressbar" style="width: ${riskScore}%">
                            ${riskScore}%
                        </div>
                    </div>
                </div>
                ${riskFactorsHtml}
                ${recommendationsHtml}
            `);
        } else {
            $('#academicRiskCard').html('<p class="text-muted text-center">Unable to load risk assessment</p>');
        }
    }, function(error) {
        $('#academicRiskCard').html('<p class="text-danger text-center">Error loading risk assessment</p>');
    });
}

$('#mainTabs').on('shown.bs.tab', function(e) {
    const target = $(e.target).attr('data-bs-target');
    if (target === '#aiInsights') {
        loadAIInsights();
    }
});
