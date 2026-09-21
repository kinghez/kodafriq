/**
 * Kodafriq Django Admin - Dynamic Broadcast Target Audience Helper
 * Conditionally shows/hides:
 * - target_group (only when target_type === 'GROUP')
 * - target_single_user (only when target_type === 'SINGLE_USER')
 * - target_users (only when target_type === 'MULTIPLE_USERS')
 */
(function() {
    'use strict';

    function initBroadcastAudienceController() {
        const targetTypeSelect = document.getElementById('id_target_type');
        if (!targetTypeSelect) return;

        function getRow(elemId, fallbackClass) {
            const elem = document.getElementById(elemId);
            if (elem) {
                const row = elem.closest('.form-row') || elem.closest('.fieldBox') || elem.closest('div');
                if (row) return row;
            }
            return document.querySelector('.' + fallbackClass);
        }

        const groupRow = getRow('id_target_group', 'field-target_group');
        const singleUserRow = getRow('id_target_single_user', 'field-target_single_user');
        const multipleUsersRow = getRow('id_target_users', 'field-target_users');

        function updateVisibility() {
            const currentType = targetTypeSelect.value;

            // 1. Django User Group
            if (groupRow) {
                if (currentType === 'GROUP') {
                    groupRow.style.display = '';
                } else {
                    groupRow.style.display = 'none';
                }
            }

            // 2. Single Specific User dropdown
            if (singleUserRow) {
                if (currentType === 'SINGLE_USER') {
                    singleUserRow.style.display = '';
                } else {
                    singleUserRow.style.display = 'none';
                }
            }

            // 3. Multiple Specific Users filter horizontal
            if (multipleUsersRow) {
                if (currentType === 'MULTIPLE_USERS') {
                    multipleUsersRow.style.display = '';
                } else {
                    multipleUsersRow.style.display = 'none';
                }
            }
        }

        // Run immediately
        updateVisibility();

        // Listen for user changes
        targetTypeSelect.addEventListener('change', updateVisibility);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBroadcastAudienceController);
    } else {
        initBroadcastAudienceController();
    }

    window.addEventListener('load', initBroadcastAudienceController);
})();
