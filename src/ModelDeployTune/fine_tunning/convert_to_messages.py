import json
from pathlib import Path

IN_FILE = './temp/origin_dataset.jsonl'
OUT_FILE = "./temp/dataset_message.jsonl"
# 防止收敛还是用统一的任务提示词
SYSTEM_PROMPT = "你是一个多任务助手,请严格按用户给出的任务要求和输出格式回答，不要添加额外解释。"


def canon_json_text(s: str) -> str:
    """
    把字符串形式的 JSON（如 decision/planner output）规范化成紧凑稳定格式。
    如果不是合法 JSON，就原样返回（用于 memory/identity 的自然语言输出）。
    """
    if not isinstance(s, str):
        return str(s)
    t = s.strip()
    if not t:
        return t
    try:
        obj = json.loads(t)
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return s.strip()


def build_user(task_type: str, instruction: str, inp: str) -> str:
    task = (task_type or "").upper()  # 大写-保证为空的粗壮且基本对话不要有明确的任务
    instruction = (instruction or "").strip()
    inp = (inp or "").strip()

    # 给不同任务加更强的输出约束（可选但很建议）
    extra = ""
    if task == "DECISION":
        extra = "\n输出要求：只输出JSON，不要解释。格式：{\"requires_agent\": true/false}"
    elif task == "PLANNER":
        extra = "\n输出要求：只输出JSON，不要解释。输出格式为plan_steps，其必须包含每一步的description和capability。"
    elif task == "MEMORY":
        extra = "\n输出要求：只输出画像内容；空画像输出[]；不要解释。"
    elif task == "":
        extra = "\n输出要求：直接回答用户的问题"
    if task != "":
        parts = [f"<TASK={task}>"]
    else:
        parts = []
    if instruction:
        parts.append(instruction + extra)
    else:
        parts.append(extra.strip())
    if inp:
        parts.append("\n" + inp)

    return "\n".join([p for p in parts if p is not None]).strip()


def convert_line(obj: dict) -> dict | None:
    task_type = obj.get("task_type", "")
    instruction = obj.get("instruction", "")
    inp = obj.get("input", "")
    out = obj.get("output", "")

    if not isinstance(inp, str) or not inp.strip():
        return None

    # decision/planner 输出通常是字符串 JSON；这里做一次规范化
    task_upper = (task_type or "").upper()  # 大写或者为空
    if task_upper in {"DECISION", "PLANNER"}:
        out_text = canon_json_text(out)
        # 进一步过滤：必须是合法 JSON（避免训练坏格式）
        try:
            json.loads(out_text)
        except Exception:
            return None
    else:
        out_text = (out or "").strip()

    user_text = build_user(task_type, instruction, inp)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": out_text},
        ]
    }


def convert():
    in_path = Path(IN_FILE)
    out_path = Path(OUT_FILE)

    n_in = 0
    n_out = 0
    dropped = 0
    by_task = {}

    with in_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            n_in += 1
            try:
                obj = json.loads(line)
            except Exception:
                dropped += 1
                continue

            sample = convert_line(obj)
            if sample is None:
                dropped += 1
                continue

            task = (obj.get("task_type", "") or "identity").lower()
            by_task[task] = by_task.get(task, 0) + 1

            fout.write(json.dumps(sample, ensure_ascii=False) + "\n")
            n_out += 1

    print(f"Input lines: {n_in}")
    print(f"Output lines: {n_out}")
    print(f"Dropped: {dropped}")
    print("By task:", by_task)


if __name__ == "__main__":
    convert()
