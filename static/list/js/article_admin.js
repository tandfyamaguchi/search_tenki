(() => {
  'use strict';

  // 号の選択欄を、選択された巻に登録済みの号へ更新する。
  function setIssueChoices(issueSelect, issues, selectedIssue) {
    const selectedValue = String(selectedIssue || '');
    const issueValues = new Set(issues.map((issue) => String(issue.number)));

    issueSelect.replaceChildren();
    issueSelect.append(new Option('号を選択', ''));

    // 旧データの未登録値は、変更画面で値を失わないよう候補に残す。
    if (selectedValue && !issueValues.has(selectedValue)) {
      issueSelect.append(
        new Option(
          `現在の値: ${selectedValue}号（この巻には未登録）`,
          selectedValue,
        ),
      );
    }

    issues.forEach((issue) => {
      issueSelect.append(new Option(`${issue.number}号`, issue.number));
    });
    issueSelect.value = selectedValue;
  }

  // 選択中の巻に対応する号だけをadminのJSONから読み込む。
  async function refreshIssueChoices(volumeSelect, issueSelect, selectedIssue) {
    const volume = volumeSelect.value;
    if (!volume) {
      setIssueChoices(issueSelect, [], '');
      issueSelect.disabled = true;
      return;
    }

    issueSelect.disabled = true;
    const issueUrl = new URL(issueSelect.dataset.issueUrl, window.location.origin);
    issueUrl.searchParams.set('volume', volume);

    try {
      const response = await fetch(issueUrl, {
        credentials: 'same-origin',
        headers: {'X-Requested-With': 'XMLHttpRequest'},
      });
      if (!response.ok) {
        throw new Error('号の候補を取得できませんでした。');
      }

      const data = await response.json();
      // 非同期処理中に巻を切り替えた場合、古い応答は反映しない。
      if (volumeSelect.value !== volume) {
        return;
      }
      setIssueChoices(issueSelect, data.issues || [], selectedIssue);
      issueSelect.disabled = false;
    } catch (error) {
      if (volumeSelect.value !== volume) {
        return;
      }
      setIssueChoices(issueSelect, [], '');
      issueSelect.disabled = false;
      issueSelect.setCustomValidity('号の候補を読み込めませんでした。もう一度巻を選択してください。');
    }
  }

  // 巻の変更時に号を選び直せるよう、初期表示とchangeイベントを設定する。
  function initializePublicationSelector() {
    const volumeSelect = document.getElementById('id_volume');
    const issueSelect = document.getElementById('id_no');
    if (!volumeSelect || !issueSelect || !issueSelect.dataset.issueUrl) {
      return;
    }

    const initialIssue = issueSelect.value;
    refreshIssueChoices(volumeSelect, issueSelect, initialIssue);

    volumeSelect.addEventListener('change', () => {
      issueSelect.setCustomValidity('');
      refreshIssueChoices(volumeSelect, issueSelect, '');
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initializePublicationSelector();
  });
})();
