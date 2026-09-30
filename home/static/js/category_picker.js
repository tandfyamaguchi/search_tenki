// カテゴリ選択UIの変数を外部へ公開しない。
(function () {
    'use strict';

    // 原稿種別の親要素を返す。
    function getCategoryGroups(picker) {
        return picker.querySelectorAll('[data-category-group]');
    }

    // 原稿種別内の実カテゴリ要素を返す。
    function getGroupOptions(group) {
        return group.querySelectorAll('[data-category-option]');
    }

    // 画面内の実カテゴリ要素を返す。
    function getCategoryOptions(picker) {
        return picker.querySelectorAll('[data-category-option]');
    }

    // 実カテゴリ要素内のチェックボックスを返す。
    function getCategoryInput(option) {
        return option.querySelector('[data-category-input]');
    }

    // 原稿種別の親チェックボックスを返す。
    function getGroupToggle(group) {
        return group.querySelector('[data-category-group-toggle]');
    }

    // 原稿種別の子カテゴリ一覧を返す。
    function getGroupChildren(group) {
        return group.querySelector('[data-category-group-children]');
    }

    // 原稿種別の表示名を返す。
    function getGroupLabel(group) {
        var label = group.querySelector('.category-picker__group-label');

        return label ? label.textContent.trim() : '';
    }

    // 実カテゴリの表示名を返す。
    function getCategoryLabel(option) {
        var label = option.querySelector('label');

        return label ? label.textContent.trim() : '';
    }

    // 絞り込み用の文字列を比較しやすい形にする。
    function normalizeText(value) {
        return value.trim().toLowerCase();
    }

    // カテゴリ選択UIの状態を返す。
    function getPickerState(picker) {
        return picker.categoryPickerState;
    }

    // 指定要素を含む原稿種別の親要素を返す。
    function getOptionGroup(element) {
        var currentElement = element;

        while (currentElement && currentElement !== document) {
            if (currentElement.hasAttribute && currentElement.hasAttribute('data-category-group')) {
                return currentElement;
            }
            currentElement = currentElement.parentNode;
        }

        return null;
    }

    // 原稿種別が展開状態かどうかを返す。
    function isGroupExpanded(group) {
        return group.categoryPickerExpanded === true;
    }

    // 原稿種別の展開状態を記録する。
    function setGroupExpanded(group, expanded) {
        group.categoryPickerExpanded = expanded === true;
    }

    // 原稿種別内のチェック済みカテゴリ数を返す。
    function getSelectedGroupOptionCount(group) {
        var options = getGroupOptions(group);
        var selectedCount = 0;
        var index;

        for (index = 0; index < options.length; index += 1) {
            var input = getCategoryInput(options[index]);

            if (input && input.checked) {
                selectedCount += 1;
            }
        }

        return selectedCount;
    }

    // チェック済みの実カテゴリ要素を返す。
    function getSelectedOptions(picker) {
        var options = getCategoryOptions(picker);
        var selectedOptions = [];
        var index;

        for (index = 0; index < options.length; index += 1) {
            var input = getCategoryInput(options[index]);

            if (input && input.checked) {
                selectedOptions.push(options[index]);
            }
        }

        return selectedOptions;
    }

    // 原稿種別の親チェック状態を子カテゴリへ合わせる。
    function updateGroupToggle(group) {
        var toggle = getGroupToggle(group);
        var optionCount = getGroupOptions(group).length;
        var selectedCount = getSelectedGroupOptionCount(group);

        if (!toggle) {
            return;
        }
        toggle.disabled = optionCount === 0;
        toggle.checked = optionCount > 0 && selectedCount === optionCount;
        toggle.indeterminate = selectedCount > 0 && selectedCount < optionCount;
    }

    // 原稿種別の表示と子カテゴリの展開状態を更新する。
    function updateCategoryOptions(picker) {
        var state = getPickerState(picker);
        var groups = getCategoryGroups(picker);
        var query = normalizeText(state.filter.value);
        var visibleGroupCount = 0;
        var categoryCount = 0;
        var index;

        for (index = 0; index < groups.length; index += 1) {
            var group = groups[index];
            var options = getGroupOptions(group);
            var groupMatches = getGroupLabel(group).toLowerCase().indexOf(query) !== -1;
            var matchingOptionCount = 0;
            var optionIndex;

            categoryCount += options.length;
            for (optionIndex = 0; optionIndex < options.length; optionIndex += 1) {
                var option = options[optionIndex];
                var optionMatches = getCategoryLabel(option).toLowerCase().indexOf(query) !== -1;

                if (optionMatches) {
                    matchingOptionCount += 1;
                }
                option.hidden = query !== '' && !groupMatches && !optionMatches;
            }

            var groupVisible = query === '' || groupMatches || matchingOptionCount > 0;
            var childrenVisible = query !== '' ? groupVisible : isGroupExpanded(group);
            var children = getGroupChildren(group);

            group.hidden = !groupVisible;
            if (children) {
                children.hidden = !childrenVisible;
            }
            if (groupVisible) {
                visibleGroupCount += 1;
            }
            updateGroupToggle(group);
        }

        state.noResults.hidden = query === '' || visibleGroupCount !== 0;

        return {
            categoryCount: categoryCount,
            groupCount: groups.length,
            query: query,
            visibleGroupCount: visibleGroupCount
        };
    }

    // 全選択と全解除の有効状態を更新する。
    function updateActionButtons(picker, selectedOptions, categoryCount) {
        var state = getPickerState(picker);

        state.selectAllButton.disabled = categoryCount === 0 || selectedOptions.length === categoryCount;
        state.clearButton.disabled = selectedOptions.length === 0;
    }

    // 現在の原稿種別数と選択数を読み上げ用に表示する。
    function updateStatus(picker, displayState, selectedCount) {
        var state = getPickerState(picker);
        var message;

        if (displayState.query !== '') {
            message = displayState.visibleGroupCount + '種の原稿種別を表示しています。';
        } else {
            message = displayState.groupCount + '種の原稿種別を表示しています。';
        }

        state.status.textContent = message + ' 選択中：' + selectedCount + '件。';
    }

    // 画面のカテゴリ選択状態をまとめて同期する。
    function syncCategoryPicker(picker) {
        var selectedOptions = getSelectedOptions(picker);
        var displayState = updateCategoryOptions(picker);

        updateActionButtons(picker, selectedOptions, displayState.categoryCount);
        updateStatus(picker, displayState, selectedOptions.length);
    }

    // 絞り込み文字列の変更を反映する。
    function handleFilterInput(event) {
        var picker = event.currentTarget.categoryPicker;

        if (picker) {
            syncCategoryPicker(picker);
        }
    }

    // 原稿種別を選び、配下の実カテゴリをまとめて選択または解除する。
    function handleGroupToggle(event) {
        var toggle = event.currentTarget;
        var picker = toggle.categoryPicker;
        var group = toggle.categoryGroup;
        var options = getGroupOptions(group);
        var index;

        for (index = 0; index < options.length; index += 1) {
            var input = getCategoryInput(options[index]);

            if (input && !input.disabled) {
                input.checked = toggle.checked;
            }
        }
        setGroupExpanded(group, toggle.checked);
        syncCategoryPicker(picker);
    }

    // すべての実カテゴリ候補をチェックする。
    function handleSelectAll(event) {
        var button = event.currentTarget;
        var picker = button.categoryPicker;
        var options = getCategoryOptions(picker);
        var groups = getCategoryGroups(picker);
        var index;

        event.preventDefault();
        for (index = 0; index < options.length; index += 1) {
            var input = getCategoryInput(options[index]);

            if (input && !input.disabled) {
                input.checked = true;
            }
        }
        for (index = 0; index < groups.length; index += 1) {
            setGroupExpanded(groups[index], false);
        }
        syncCategoryPicker(picker);
    }

    // すべての実カテゴリ候補のチェックを外す。
    function handleClear(event) {
        var button = event.currentTarget;
        var picker = button.categoryPicker;
        var options = getCategoryOptions(picker);
        var groups = getCategoryGroups(picker);
        var index;

        event.preventDefault();
        for (index = 0; index < options.length; index += 1) {
            var input = getCategoryInput(options[index]);

            if (input && !input.disabled) {
                input.checked = false;
            }
        }
        for (index = 0; index < groups.length; index += 1) {
            setGroupExpanded(groups[index], false);
        }
        syncCategoryPicker(picker);
    }

    // 実カテゴリの変更を親原稿種別へ反映する。
    function handleOptionChange(event) {
        var input = event.currentTarget;
        var picker = input.categoryPicker;
        var group = getOptionGroup(input);

        if (picker) {
            if (group) {
                setGroupExpanded(group, true);
            }
            syncCategoryPicker(picker);
        }
    }

    // 親フォームを見つける。
    function findParentForm(element) {
        var parent = element.parentNode;

        while (parent && parent.tagName !== 'FORM') {
            parent = parent.parentNode;
        }

        return parent;
    }

    // リセット後のカテゴリ表示を同期する。
    function refreshPickerAfterFormReset() {
        var groups = getCategoryGroups(this);
        var index;

        for (index = 0; index < groups.length; index += 1) {
            setGroupExpanded(groups[index], false);
        }
        syncCategoryPicker(this);
    }

    // フォームのリセット後にカテゴリ表示を更新する。
    function handleFormReset(event) {
        var picker = event.currentTarget.categoryPicker;

        if (picker) {
            window.setTimeout(refreshPickerAfterFormReset.bind(picker), 0);
        }
    }

    // カテゴリ選択UIにイベントを設定する。
    function setupCategoryPicker(picker) {
        var filter = picker.querySelector('#category-filter');
        var optionsList = picker.querySelector('#category-options');
        var selectAllButton = picker.querySelector('#category-select-all');
        var clearButton = picker.querySelector('#category-clear');
        var noResults = picker.querySelector('#category-no-results');
        var status = picker.querySelector('#category-match-status');
        var groups;
        var form;
        var index;

        if (!filter || !optionsList || !selectAllButton || !clearButton || !noResults || !status) {
            return;
        }

        picker.categoryPickerState = {
            clearButton: clearButton,
            filter: filter,
            noResults: noResults,
            selectAllButton: selectAllButton,
            status: status
        };
        filter.categoryPicker = picker;
        selectAllButton.categoryPicker = picker;
        clearButton.categoryPicker = picker;
        filter.addEventListener('input', handleFilterInput);
        selectAllButton.addEventListener('click', handleSelectAll);
        clearButton.addEventListener('click', handleClear);

        groups = getCategoryGroups(picker);
        for (index = 0; index < groups.length; index += 1) {
            var group = groups[index];
            var toggle = getGroupToggle(group);
            var options = getGroupOptions(group);
            var optionIndex;

            setGroupExpanded(group, getSelectedGroupOptionCount(group) > 0);
            if (toggle) {
                toggle.categoryGroup = group;
                toggle.categoryPicker = picker;
                toggle.addEventListener('change', handleGroupToggle);
            }
            for (optionIndex = 0; optionIndex < options.length; optionIndex += 1) {
                var input = getCategoryInput(options[optionIndex]);

                if (input) {
                    input.categoryPicker = picker;
                    input.addEventListener('change', handleOptionChange);
                }
            }
        }

        form = findParentForm(picker);
        if (form) {
            form.categoryPicker = picker;
            form.addEventListener('reset', handleFormReset);
        }
        syncCategoryPicker(picker);
    }

    // ページ内のカテゴリ選択UIを初期化する。
    function initializeCategoryPickers() {
        var pickers = document.querySelectorAll('[data-category-picker]');
        var index;

        for (index = 0; index < pickers.length; index += 1) {
            setupCategoryPicker(pickers[index]);
        }
    }

    // DOMの読み込み完了後にカテゴリ選択UIを初期化する。
    function startCategoryPicker() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeCategoryPickers);
        } else {
            initializeCategoryPickers();
        }
    }

    startCategoryPicker();
}());
