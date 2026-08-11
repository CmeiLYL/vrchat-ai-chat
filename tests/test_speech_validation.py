"""语音有效性判断：过滤 whisper 对音乐/环境音的幻觉。"""
import numpy as np

from vrchat_ai.infrastructure.whisper_stt import WhisperRecognizer, is_valid_speech


def test_empty_text_invalid():
    assert not is_valid_speech("", 0.1, -0.5)
    assert not is_valid_speech("   ", 0.1, -0.5)


def test_clear_speech_valid():
    assert is_valid_speech("你好呀", 0.05, -0.4)


def test_music_high_no_speech_prob_invalid():
    """音乐：whisper 虽幻觉出文本，但 no_speech_prob 高 → 判定无效。"""
    assert not is_valid_speech("啦啦啦哼唱着莫名的歌词", 0.85, -0.6)


def test_low_confidence_hallucination_invalid():
    """低置信度乱码 → 无效。"""
    assert not is_valid_speech("唔嗯嗯啊", 0.3, -3.0)


def test_custom_threshold():
    """可调阈值：no_speech_threshold 调低后，一般语音也可能被过滤。"""
    assert not is_valid_speech("你好", 0.5, -0.4, no_speech_threshold=0.3)
    assert is_valid_speech("你好", 0.5, -0.4, no_speech_threshold=0.6)


# ---------- WhisperRecognizer.transcribe 集成（mock 模型，贴近真实 faster-whisper API） ----------
# 注意：真实 API 里 no_speech_prob 在 Segment 上，TranscriptionInfo 没有该字段

class _FakeSeg:
    def __init__(self, text, prob, no_speech_prob):
        self.text = text
        self.avg_logprob = prob
        self.no_speech_prob = no_speech_prob


class _FakeInfo:
    """模拟 TranscriptionInfo：只有 language/duration 等，无 no_speech_prob。"""

    def __init__(self):
        self.language = "zh"
        self.duration = 1.0


def _make_recognizer(fake_transcribe):
    rec = WhisperRecognizer.__new__(WhisperRecognizer)  # 跳过真实模型加载
    rec._sample_rate = 16000
    rec._language = "zh"
    rec._no_speech_threshold = 0.6
    rec._model = type("FakeModel", (), {"transcribe": fake_transcribe})()
    return rec


def test_transcribe_handles_generator_once():
    """segments 是生成器只能遍历一次：若实现二次遍历会拿到空，返回空串。"""
    def fake(self, audio, **kw):  # noqa: ARG001 —— mock 方法，self 为假模型实例
        return (_FakeSeg("你好", -0.5, 0.05) for _ in range(1)), _FakeInfo()

    rec = _make_recognizer(fake)
    assert rec.transcribe(np.zeros(16000, dtype=np.float32)) == "你好"


def test_transcribe_filters_music_hallucination():
    """音乐幻觉：no_speech_prob 高 → 返回空串，不进入 LLM 链路。"""
    def fake(self, audio, **kw):  # noqa: ARG001
        return (_FakeSeg("啦啦啦莫名歌词", -0.8, 0.85) for _ in range(1)), _FakeInfo()

    rec = _make_recognizer(fake)
    assert rec.transcribe(np.zeros(16000, dtype=np.float32)) == ""


def test_transcribe_filters_low_confidence():
    """低置信度幻觉（avg_logprob 过低）→ 返回空串。"""
    def fake(self, audio, **kw):  # noqa: ARG001
        return (_FakeSeg("唔嗯嗯啊", -3.2, 0.1) for _ in range(1)), _FakeInfo()

    rec = _make_recognizer(fake)
    assert rec.transcribe(np.zeros(16000, dtype=np.float32)) == ""


def test_transcribe_multi_segment_max_no_speech_wins():
    """多段时取 no_speech_prob 最大值：任一段无语音概率高 → 整段无效。"""
    def fake(self, audio, **kw):  # noqa: ARG001
        def gen():
            yield _FakeSeg("有人说了一句", -0.6, 0.1)
            yield _FakeSeg("音乐伴奏", -0.7, 0.9)   # 这段是无语音的音乐
        return gen(), _FakeInfo()

    rec = _make_recognizer(fake)
    assert rec.transcribe(np.zeros(16000, dtype=np.float32)) == ""
