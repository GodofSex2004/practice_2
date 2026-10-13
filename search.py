"""Модуль поиска подстрок в строке.

Реализован алгоритм Рабина-Карпа (вариант 4) с собственной
реализацией кольцевого (скользящего) хеша, а также функция поиска
``search`` с сигнатурой, описанной в задании практической работы.
"""

import functools
import logging
import time
from typing import Callable, Optional, Sequence, TypeVar, Union

__all__ = ['RollingHash', 'rabin_karp', 'log_execution_time', 'search', 'SearchResult']

logger = logging.getLogger(__name__)

SubStrings = Union[str, list[str], tuple[str, ...]]
SearchResult = Optional[Union[tuple[int, ...], dict[str, Optional[tuple[int, ...]]]]]

_F = TypeVar('_F', bound=Callable)


def log_execution_time(func: _F) -> _F:
    """Декоратор, логирующий время выполнения функции.

    Args:
        func: декорируемая функция.

    Returns:
        Обёртка, замеряющая время работы ``func`` и пишущая его
        в лог с именем функции.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            logger.info('Время выполнения %s(): %.6f с', func.__name__, elapsed)

    return wrapper  # type: ignore[return-value]


class RollingHash:
    """Кольцевой (скользящий) хеш строки.

    Хеш вычисляется как полиномиальный хеш::

        h(s) = (s[0] * BASE^(m-1) + s[1] * BASE^(m-2) + ... + s[m-1]) mod MODULUS

    после сдвига окна на один символ хеш пересчитывается за O(1)
    без повторного прохода по окну.
    """

    BASE: int = 131
    MODULUS: int = (1 << 61) - 1

    def __init__(self, window: str) -> None:
        """Инициализирует хеш окна ``window``.

        Args:
            window: строка-окно, хеш которой вычисляется.
        """
        self._length = len(window)
        self._power = pow(self.BASE, self._length - 1, self.MODULUS) if self._length else 0
        self._hash = 0
        for char in window:
            self._hash = (self._hash * self.BASE + ord(char)) % self.MODULUS

    @property
    def value(self) -> int:
        """int: Текущее значение хеша окна."""
        return self._hash

    def roll(self, leaving: str, entering: str) -> int:
        """Сдвигает окно на один символ вправо.

        Из текущего хеша исключается первый символ окна,
        остальная часть умножается на основание и дополняется
        новым символом.

        Args:
            leaving: символ, выходящий из окна (левый край).
            entering: символ, входящий в окно (правый край).

        Returns:
            Новое значение хеша.
        """
        self._hash = (self._hash - ord(leaving) * self._power) % self.MODULUS
        self._hash = (self._hash * self.BASE + ord(entering)) % self.MODULUS
        return self._hash


def rabin_karp(string: str, sub_string: str) -> list[int]:
    """Ищет все вхождения подстроки алгоритмом Рабина-Карпа.

    Сравнение хешей дополняется прямым сравнением символов,
    поэтому ложные срабатывания из-за коллизий хеша исключены.

    Args:
        string: исходная строка.
        sub_string: искомая подстрока.

    Returns:
        Список индексов начала каждого вхождения в порядке
        возрастания. Если вхождений нет, список пуст.
    """
    text_length = len(string)
    pattern_length = len(sub_string)
    if pattern_length == 0 or pattern_length > text_length:
        return []

    target_hash = RollingHash(sub_string).value
    window = RollingHash(string[:pattern_length])
    matches: list[int] = []

    for position in range(text_length - pattern_length + 1):
        if window.value == target_hash and string[position:position + pattern_length] == sub_string:
            matches.append(position)
        if position < text_length - pattern_length:
            window.roll(string[position], string[position + pattern_length])

    return matches


def _locate(text: str, patterns: Sequence[str], case_sensitivity: bool) -> list[tuple[int, int]]:
    """Находит все вхождения подстрок в строке.

    Args:
        text: строка, в которой выполняется поиск.
        patterns: искомые подстроки.
        case_sensitivity: флаг чувствительности к регистру.

    Returns:
        Список пар ``(индекс начала, номер подстроки)``,
        отсортированный по возрастанию индекса.
    """
    located: list[tuple[int, int]] = []
    for pattern_index, pattern in enumerate(patterns):
        needle = pattern if case_sensitivity else pattern.lower()
        for index in rabin_karp(text, needle):
            located.append((index, pattern_index))
    located.sort(key=lambda item: item[0])
    return located


def _group_matches(located: list[tuple[int, int]],
                   method: str,
                   count: Optional[int],
                   patterns_count: int) -> list[list[int]]:
    """Упорядочивает и группирует совпадения по номерам подстрок.

    Args:
        located: пары ``(индекс, номер подстроки)`` в порядке возрастания.
        method: направление поиска ``'first'`` или ``'last'``.
        count: ограничение на количество совпадений ``k``.
        patterns_count: количество искомых подстрок.

    Returns:
        Список из ``patterns_count`` списков индексов — по одному
        списку на каждую подстроку.
    """
    ordered = located[::-1] if method == 'last' else located
    if count is not None:
        ordered = ordered[:max(count, 0)]

    grouped: list[list[int]] = [[] for _ in range(patterns_count)]
    for index, pattern_index in ordered:
        grouped[pattern_index].append(index)
    return grouped


@log_execution_time
def search(string: str,
           sub_string: SubStrings,
           case_sensitivity: bool = False,
           method: str = 'first',
           count: Optional[int] = None) -> SearchResult:
    """Ищет вхождения одной или нескольких подстрок в строке.

    Args:
        string: исходная строка.
        sub_string: подстрока или список подстрок для поиска.
        case_sensitivity: флаг чувствительности к регистру
            (``False`` — поиск без учёта регистра).
        method: направление поиска, ``'first'`` — от начала строки,
            ``'last'`` — от конца строки.
        count: максимальное количество найденных совпадений ``k``;
            ``None`` — без ограничения.

    Returns:
        Для одной подстроки — кортеж индексов начала вхождений
        (или ``None``, если вхождений нет). Для нескольких подстрок —
        словарь ``{подстрока: кортеж индексов}``, при отсутствии
        вхождений значение ``None``.

    Raises:
        ValueError: если ``method`` не равен ``'first'`` или ``'last'``.
        ValueError: если ``count`` задан и не является положительным целым.
    """
    if method not in ('first', 'last'):
        raise ValueError(f"Недопустимый метод поиска: {method!r}, ожидается 'first' или 'last'")
    if count is not None and count <= 0:
        raise ValueError(f'Недопустимое количество вхождений: {count!r}, ожидается положительное целое')

    if not string:
        return None

    is_many = not isinstance(sub_string, str)
    patterns = list(dict.fromkeys(sub_string)) if is_many else [sub_string]
    text = string if case_sensitivity else string.lower()

    located = _locate(text, patterns, case_sensitivity)
    grouped = _group_matches(located, method, count, len(patterns))

    if not is_many:
        found = grouped[0]
        return tuple(found) if found else None

    return {pattern: tuple(found) if found else None
            for pattern, found in zip(patterns, grouped)}
