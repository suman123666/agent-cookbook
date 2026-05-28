from typing import Dict, Any, List, Union, Hashable
import copy


def merge_dicts(a: Dict[Hashable, Any], b: Dict[Hashable, Any], strategy: str = "override") -> Dict[Hashable, Any]:
    """
    深度合并两个字典，支持嵌套字典和列表去重合并（保持顺序）。
    
    :param a: 基础字典，作为合并的基准；必须为 dict 类型
    :param b: 待合并字典，其键值将按策略融入 a；必须为 dict 类型
    :param strategy: 合并策略，取值为 "override"（默认，b 中同名键覆盖 a 的对应值，但对列表执行去重合并）、
                     "ignore"（保留 a 的值，忽略 b 中同名键）、
                     "raise"（遇到类型冲突的同名键值时抛出 TypeError）。
                     若传入非法策略字符串，则抛出 ValueError
    :return: 一个全新字典，是 a 和 b 按指定策略深度合并后的结果；不修改原始 a 或 b
    :raises TypeError: 当 a 或 b 非 dict 类型、或 strategy="raise" 且遇到不可合并的同名键值（如 int vs list、None vs str、set vs tuple 等）时抛出
    :raises ValueError: 当 strategy 参数不是 "override"、"ignore" 或 "raise" 之一时抛出
    """
    # 输入类型检查
    if not isinstance(a, dict):
        raise TypeError(f"Expected 'a' to be a dict, got {type(a).__name__}")
    if not isinstance(b, dict):
        raise TypeError(f"Expected 'b' to be a dict, got {type(b).__name__}")

    # 策略合法性检查
    if strategy not in ("override", "ignore", "raise"):
        raise ValueError(f"Unknown strategy: '{strategy}'. Must be one of 'override', 'ignore', or 'raise'.")

    # 初始化 result：对 a 全量 deep copy，确保不污染原 a
    result: Dict[Hashable, Any] = copy.deepcopy(a)

    for key, b_value in b.items():
        if key in result:
            a_value = result[key]
            if isinstance(a_value, dict) and isinstance(b_value, dict):
                # 递归合并嵌套字典：传入 deep copy 避免污染原 a_value
                result[key] = merge_dicts(copy.deepcopy(a_value), copy.deepcopy(b_value), strategy)
            elif isinstance(a_value, list) and isinstance(b_value, list):
                # 列表合并：保持顺序、去重（基于 == 比较，支持嵌套 dict/list）
                if strategy == "override":
                    # deep copy a_value 以避免污染原 a
                    merged_list = copy.deepcopy(a_value)
                    for item in b_value:
                        # 线性查找是否已存在（支持不可哈希项，如含 NaN 的 float、自定义对象）
                        found = False
                        for existing in merged_list:
                            try:
                                if existing == item:
                                    found = True
                                    break
                            except Exception:
                                # 比较异常（如自定义 __eq__ 抛异常），视为不等
                                pass
                        if not found:
                            merged_list.append(copy.deepcopy(item))  # deep copy item 防止污染 b
                    result[key] = merged_list
                elif strategy == "ignore":
                    # 显式保留 a_value（已 deep copied 到 result[key]，无需再操作）
                    pass
                elif strategy == "raise":
                    raise TypeError(f"Cannot merge values for key '{key}': {a_value!r} (type {type(a_value).__name__}) and {b_value!r} (type {type(b_value).__name__})")
            else:
                # 类型冲突：a_value 与 b_value 均非 dict 且非 list（如 int vs str, None vs bool, float vs list, set vs tuple 等）
                if strategy == "override":
                    result[key] = copy.deepcopy(b_value)
                elif strategy == "ignore":
                    # 已由 copy.deepcopy(a) 初始化，无需操作
                    pass
                elif strategy == "raise":
                    raise TypeError(f"Cannot merge values for key '{key}': {a_value!r} (type {type(a_value).__name__}) and {b_value!r} (type {type(b_value).__name__})")
        else:
            # key 不在 a 中，deep copy b_value（防止后续修改影响 b）
            result[key] = copy.deepcopy(b_value)

    return result


if __name__ == "__main__":
    # 示例 1: override 策略 —— 基本嵌套字典
    a1 = {"x": 1, "y": {"z": 2}}
    b1 = {"x": 99, "y": {"z": 88, "w": 3}}
    print("override (dict):", merge_dicts(a1, b1, "override"))

    # 示例 2: override 策略 —— 列表合并（核心场景：保持顺序、去重）
    a2 = {"nums": [1, 2, 3], "tags": ["a", "b"]}
    b2 = {"nums": [2, 3, 4, 5], "tags": ["b", "c"]}
    print("override (list):", merge_dicts(a2, b2, "override"))

    # 示例 3: ignore 策略
    a3 = {"x": 1, "y": [1, 2]}
    b3 = {"x": 99, "y": [3, 4]}
    print("ignore:", merge_dicts(a3, b3, "ignore"))

    # 示例 4: raise 策略 —— 基础类型冲突（None vs int）
    a4 = {"x": None, "data": [1, 2]}
    b4 = {"x": 42, "data": {"nested": True}}
    try:
        print("raise (None vs int):", merge_dicts(a4, b4, "raise"))
    except TypeError as e:
        print("raise error (None vs int):", e)