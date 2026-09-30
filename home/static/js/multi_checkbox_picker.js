// 巻・号のチェックボックス操作を外部へ公開しない。
(function () {
    'use strict';

    // 選択UI内のチェックボックスを返す。
    function getPickerInputs(picker) {
        return picker.querySelectorAll('input[data-checkbox-picker-input]');
    }

    // 操作可能なチェックボックスを配列で返す。
    function getSelectableInputs(picker) {
        var inputs = getPickerInputs(picker);
        var selectableInputs = [];
        var index;

        for (index = 0; index < inputs.length; index += 1) {
            if (!inputs[index].disabled) {
                selectableInputs.push(inputs[index]);
            }
        }

        return selectableInputs;
    }

    // チェック済みの入力数を返す。
    function getCheckedInputCount(inputs) {
        var checkedCount = 0;
        var index;

        for (index = 0; index < inputs.length; index += 1) {
            if (inputs[index].checked) {
                checkedCount += 1;
            }
        }

        return checkedCount;
    }

    // 選択UIの保持状態を返す。
    function getPickerState(picker) {
        return picker.checkboxPickerState;
    }

    // 全選択と全解除ボタンの有効状態を更新する。
    function updateActionButtons(picker, selectableInputs, checkedCount) {
        var state = getPickerState(picker);

        state.selectAllButton.disabled = selectableInputs.length === 0 || checkedCount === selectableInputs.length;
        state.clearButton.disabled = checkedCount === 0;
    }

    // 選択数を画面と支援技術へ表示する。
    function updateStatus(picker, selectableCount, checkedCount) {
        var status = getPickerState(picker).status;

        if (selectableCount === 0) {
            status.textContent = '選択できる候補がありません。';
            return;
        }

        status.textContent = '選択中：' + checkedCount + '件 / 全' + selectableCount + '件。';
    }

    // 選択UI全体の表示状態を同期する。
    function syncCheckboxPicker(picker) {
        var selectableInputs = getSelectableInputs(picker);
        var checkedCount = getCheckedInputCount(selectableInputs);

        updateActionButtons(picker, selectableInputs, checkedCount);
        updateStatus(picker, selectableInputs.length, checkedCount);
    }

    // 指定した入力群をまとめて選択または解除する。
    function setInputsChecked(inputs, checked) {
        var index;

        for (index = 0; index < inputs.length; index += 1) {
            inputs[index].checked = checked;
        }
    }

    // この選択UIの候補をすべてチェックする。
    function handleSelectAll(event) {
        var picker = event.currentTarget.checkboxPicker;

        event.preventDefault();
        if (!picker) {
            return;
        }

        setInputsChecked(getSelectableInputs(picker), true);
        syncCheckboxPicker(picker);
    }

    // この選択UIの候補をすべて解除する。
    function handleClear(event) {
        var picker = event.currentTarget.checkboxPicker;

        event.preventDefault();
        if (!picker) {
            return;
        }

        setInputsChecked(getSelectableInputs(picker), false);
        syncCheckboxPicker(picker);
    }

    // 個別チェックの変更を表示へ反映する。
    function handleInputChange(event) {
        var picker = event.currentTarget.checkboxPicker;

        if (picker) {
            syncCheckboxPicker(picker);
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

    // フォーム内の選択UIをリセット後の値へ同期する。
    function syncFormPickersAfterReset(form) {
        var pickers = form.checkboxPickers || [];
        var index;

        for (index = 0; index < pickers.length; index += 1) {
            syncCheckboxPicker(pickers[index]);
        }
    }

    // フォームの標準リセット完了後に表示を更新する。
    function handleFormReset(event) {
        window.setTimeout(syncFormPickersAfterReset.bind(null, event.currentTarget), 0);
    }

    // 選択UIを親フォームのリセット監視へ登録する。
    function registerPickerWithForm(form, picker) {
        if (!form.checkboxPickers) {
            form.checkboxPickers = [];
            form.addEventListener('reset', handleFormReset);
        }

        form.checkboxPickers.push(picker);
    }

    // 個別のチェックボックス選択UIに操作を設定する。
    function setupCheckboxPicker(picker) {
        var inputs = getPickerInputs(picker);
        var selectAllButton = picker.querySelector('[data-checkbox-picker-select-all]');
        var clearButton = picker.querySelector('[data-checkbox-picker-clear]');
        var status = picker.querySelector('[data-checkbox-picker-status]');
        var form;
        var index;

        if (picker.checkboxPickerInitialized || !selectAllButton || !clearButton || !status) {
            return;
        }

        picker.checkboxPickerInitialized = true;
        picker.checkboxPickerState = {
            clearButton: clearButton,
            selectAllButton: selectAllButton,
            status: status
        };
        selectAllButton.checkboxPicker = picker;
        clearButton.checkboxPicker = picker;
        selectAllButton.addEventListener('click', handleSelectAll);
        clearButton.addEventListener('click', handleClear);

        for (index = 0; index < inputs.length; index += 1) {
            inputs[index].checkboxPicker = picker;
            inputs[index].addEventListener('change', handleInputChange);
        }

        form = findParentForm(picker);
        if (form) {
            registerPickerWithForm(form, picker);
        }
        syncCheckboxPicker(picker);
    }

    // ページ内のチェックボックス選択UIを初期化する。
    function initializeCheckboxPickers() {
        var pickers = document.querySelectorAll('[data-checkbox-picker]');
        var index;

        for (index = 0; index < pickers.length; index += 1) {
            setupCheckboxPicker(pickers[index]);
        }
    }

    // DOMの読み込み完了後に選択UIを初期化する。
    function startCheckboxPicker() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeCheckboxPickers);
        } else {
            initializeCheckboxPickers();
        }
    }

    startCheckboxPicker();
}());
