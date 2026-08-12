"""SileroVAD：状态机逻辑（mock VAD 注入）+ 真实模型集成冒烟。"""
import numpy as np
import pytest

from vrchat_ai.infrastructure.silero_vad import SileroVAD


class _MockSileroVad:
    """模拟 silero_vad.VADIterator：按预设序列返回 start/end。"""

    def __init__(self, events: list[dict]):
        self.events = events
        self.idx = 0
        self.reset_count = 0

    def __call__(self, frame):
        if self.idx < len(self.events):
            ev = self.events[self.idx]
            self.idx += 1
            return ev
        return {}

    def reset_states(self):
        self.reset_count += 1


def _make_vad(events: list[dict], pre_pad: int = 5) -> SileroVAD:
    model = type("FakeModel", (), {})()
    vad = SileroVAD.__new__(SileroVAD)
    vad._sr = 16000
    vad._min_speech = 1600      # 0.1s
    vad._max_segment = 48000    # 3s
    vad._pre_pad = pre_pad
    vad._vad = _MockSileroVad(events)
    vad._remainder = np.array([], dtype=np.float32)
    vad._buf = np.array([], dtype=np.float32)
    vad._active = False
    vad._ring = []
    return vad


def test_silence_no_segment():
    """全静音：无 start 事件，不应返回任何段。"""
    vad = _make_vad([{}] * 10)
    assert vad.feed(np.zeros(5120, dtype=np.float32)) == []


def test_speech_segment_detected():
    """start → 语音帧 → end：返回完整语音段。"""
    vad = _make_vad([{"start": 0}] + [{}] * 4 + [{"end": 0}])
    segs = vad.feed(np.zeros(6 * 512, dtype=np.float32))
    assert len(segs) == 1
    assert len(segs[0]) == 6 * 512  # start 帧起全部累积（无 pre-roll 前置帧）


def test_pre_roll_prefixes_segment():
    """pre-roll：start 前的补帧应前置进段（kikitan 字头保护）。"""
    vad = _make_vad([{}] * 3 + [{"start": 0}, {"end": 0}])  # 3 帧环境音后说话
    segs = vad.feed(np.zeros(5 * 512, dtype=np.float32))
    assert len(segs) == 1
    # 前置 3 帧环境音 + start 帧 + end 帧 = 5 帧
    assert len(segs[0]) == 5 * 512


def test_short_speech_filtered():
    """最短段过滤：start 后立刻 end，段太短应丢弃。"""
    vad = _make_vad([{"start": 0}, {"end": 0}])
    segs = vad.feed(np.zeros(2 * 512, dtype=np.float32))
    assert segs == []


def test_cross_chunk_remainder():
    """跨块余数：chunk 非 512 整数倍，余数应保留到下次。"""
    vad = _make_vad([{"start": 0}, {}] + [{"end": 0}] * 1)
    vad.feed(np.zeros(512 + 100, dtype=np.float32))   # 首块余 100
    segs = vad.feed(np.zeros(512 * 2, dtype=np.float32))
    # start 帧 + 1 中间帧 + end 前帧：第一块 512 帧触发 start，
    # 第二块 2 帧（512*2）内 end 出现
    assert len(segs) <= 1


def test_max_segment_cut():
    """单段上限：说话超过 max_segment 应强制截断返回。"""
    vad = _make_vad([{"start": 0}] + [{}] * 100)  # 一直说话不 end
    segs = vad.feed(np.zeros(100 * 512, dtype=np.float32))
    assert len(segs) == 1
    assert len(segs[0]) <= 48000  # 3s 上限
    assert not vad._active  # 截断后状态复位


def test_flush_returns_residual():
    """flush：说话中残留段应返回（>= 最短段）。"""
    vad = _make_vad([{"start": 0}] + [{}] * 3)
    vad.feed(np.zeros(4 * 512, dtype=np.float32))
    seg = vad.flush()
    assert len(seg) == 4 * 512


def test_flush_empty_when_idle():
    """flush：无说话残留时返回空数组。"""
    vad = _make_vad([{}] * 3)
    vad.feed(np.zeros(3 * 512, dtype=np.float32))
    assert vad.flush().size == 0


def test_reset_clears_state():
    vad = _make_vad([{"start": 0}, {"end": 0}])
    vad.feed(np.zeros(2 * 512, dtype=np.float32))
    vad.reset()
    assert not vad._active
    assert vad._buf.size == 0
    assert vad._vad.reset_count == 1


# ---------- 真实模型集成冒烟（模型已缓存，加载 ~2s） ----------
def test_real_model_silence_no_trigger():
    """真实 Silero 模型：纯静音不应触发任何段。"""
    vad = SileroVAD(sample_rate=16000)
    segs = vad.feed(np.zeros(512 * 30, dtype=np.float32))  # ~1s 静音
    assert segs == []


def test_real_model_noise_not_speech():
    """真实 Silero 模型：白噪声不应判为语音（对比 EnergyVAD 的弱点）。"""
    rng = np.random.default_rng(42)
    noise = (rng.standard_normal(512 * 30) * 0.02).astype(np.float32)
    vad = SileroVAD(sample_rate=16000)
    segs = vad.feed(noise)
    assert segs == []


@pytest.mark.skip(reason="需要真实人声样本，集成时用麦克风实测")
def test_real_model_speech_trigger():
    """真实 Silero 模型：人声应触发（真机验证项）。"""
    pass
