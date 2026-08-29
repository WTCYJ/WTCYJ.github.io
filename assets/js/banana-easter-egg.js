(() => {
  const target = 1013;
  const trigger = document.querySelector('#banana-trigger');
  const hint = document.querySelector('#banana-hint');
  const progress = document.querySelector('#banana-progress');
  const reward = document.querySelector('#banana-reward');
  const close = document.querySelector('#banana-close');
  const take = document.querySelector('#banana-take');
  const taken = document.querySelector('#banana-taken');

  if (!trigger || !reward) return;

  let count = 0;
  let unlocked = false;

  const openReward = () => {
    if (typeof reward.showModal === 'function') reward.showModal();
    else reward.setAttribute('open', '');
    close?.focus();
  };

  trigger.addEventListener('click', () => {
    if (unlocked) {
      openReward();
      return;
    }

    count += 1;
    progress.textContent = `바나나를 ${count}번 눌렀습니다.`;
    trigger.classList.remove('is-tapped');
    void trigger.offsetWidth;
    trigger.classList.add('is-tapped');

    if (count === 10) hint.textContent = '설마 계속 누를 생각은 아니지?';
    if (count === 100) hint.textContent = '원숭이가 지켜보고 있다.';
    if (count === 500) hint.textContent = '여기까지 왔다면 멈추기엔 늦었다.';
    if (count === 1000) hint.textContent = '거의 다 익었다.';

    if (count === target) {
      unlocked = true;
      hint.textContent = '바나나 금고가 열렸다!';
      trigger.classList.add('is-unlocked');
      openReward();
    }
  });

  close?.addEventListener('click', () => reward.close());
  reward.addEventListener('click', (event) => {
    if (event.target === reward) reward.close();
  });
  take?.addEventListener('click', () => {
    taken.textContent = '바나나를 챙겼습니다. 잘 보관하세요.';
  });
})();
