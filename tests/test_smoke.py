import numpy as np
import pytest
import torch

from netresearch.models import MODEL_ORDER, SHARED_TO_INDIVIDUAL, WIDTH_FROM, build_model, count_params
from netresearch.spec import N_OUT, OBS_SHAPE
from netresearch.tasks import TASKS, make_task
from netresearch.train import evaluate_control, reset_state, run_sequence

torch.set_num_threads(1)


@pytest.mark.parametrize("name", list(TASKS))
def test_task_shapes(name):
    task = make_task(name)
    spec = task.spec
    rng = np.random.default_rng(0)
    if spec.kind == "supervised":
        b = task.sample(4, rng)
        T = spec.seq_len
        assert b["obs"].shape == (T, 4) + OBS_SHAPE
        assert set(np.unique(b["obs"])) <= {0.0, 1.0}
        assert b["mask"].shape == (T, 4)
        if spec.head == "class":
            assert b["target"].shape == (T, 4) and b["target"].max() < spec.n_out
        else:
            assert b["target"].shape == (T, 4, spec.n_out)
    else:
        env = task.make_env(3, seed=0)
        for _ in range(50):
            o = env.obs()
            assert o.shape == (3,) + OBS_SHAPE and set(np.unique(o)) <= {0.0, 1.0}
            a = env.expert()
            assert all(x in spec.valid_actions for x in a)
            env.step(a)


@pytest.mark.parametrize("name", MODEL_ORDER)
def test_model_io_and_params(name):
    m = build_model(name, 100_000)
    if name in WIDTH_FROM:                     # equal-width variants: width of the shared partner, more params
        assert m.width_used == build_model(WIDTH_FROM[name], 100_000).width_used
        assert count_params(m) > 1.1e5
    else:
        assert 0.9e5 < count_params(m) < 1.1e5
    x = torch.rand(2, 5, *OBS_SHAPE).round()
    out, st = run_sequence(m, x, resets=torch.zeros(2, 5))
    assert out.shape == (2, 5, N_OUT) and torch.isfinite(out).all()
    out.sum().backward()


@pytest.mark.parametrize("name", [m for m in MODEL_ORDER if build_model(m, 20_000).stateful])
def test_state_reset_equals_fresh_start(name):
    """After a reset, a stateful model must behave exactly like a freshly initialised one."""
    m = build_model(name, 20_000)
    m.eval()
    x = torch.rand(6, 3, *OBS_SHAPE).round()
    resets = torch.zeros(6, 3)
    resets[3] = 1.0
    with torch.no_grad():
        a, _ = run_sequence(m, x, resets=resets)
        b, _ = run_sequence(m, x[3:])
    assert torch.allclose(a[3:], b, atol=1e-5)
    s = m.init_state(3)
    assert all((t == 0).all() for t in reset_state(s, torch.zeros(3)))


def test_experts_beat_random():
    for name in ["paddle", "bricks", "racer", "maze"]:
        task = make_task(name)
        r, _ = evaluate_control(None, task, n_envs=8, policy="random")
        e, _ = evaluate_control(None, task, n_envs=8, policy="expert")
        assert e > r, name


@pytest.mark.parametrize("name", list(SHARED_TO_INDIVIDUAL))
def test_expand_shared_is_identical(name):
    from netresearch.analysis import expand_shared, position_grad_stats
    m = build_model(name, 20_000)
    ind = expand_shared(m, name)
    x = torch.rand(3, 4, *OBS_SHAPE).round()
    a, _ = run_sequence(m, x)
    b, _ = run_sequence(ind, x)
    assert torch.allclose(a, b, atol=1e-5)
    st = position_grad_stats(m, name, lambda mm: run_sequence(mm, x)[0].pow(2).mean())
    assert -1 <= st["mean_cos"] <= 1 and len(st["align"]) > 1
