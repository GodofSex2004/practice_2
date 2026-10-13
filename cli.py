"""Консольная утилита поиска подстрок (алгоритм Рабина-Карпа).

Поддерживает поиск по целевой строке и по файлу, чувствительность
к регистру, ограничение числа вхождений, поиск с начала/конца,
а также цветовое выделение найденных подстрок в выводе.
"""

import argparse
import logging
import sys
from typing import Optional, Sequence

from search import SearchResult, rabin_karp, search  # pylint: disable=E0401

try:
    from colorama import init as _colorama_init

    _colorama_init()
except ImportError:
    pass

COLORS: tuple[str, ...] = (
    '\033[31m', '\033[32m', '\033[33m', '\033[34m',
    '\033[35m', '\033[36m', '\033[91m', '\033[92m',
    '\033[93m', '\033[94m', '\033[95m', '\033[96m',
)
RESET: str = '\033[0m'
DEFAULT_MAX_LINES: int = 10


def _positive_count(value: str) -> int:
    """Преобразует значение ``-k/--count`` в положительное целое.

    Args:
        value: строка из командной строки.

    Returns:
        Положительное число вхождений.

    Raises:
        argparse.ArgumentTypeError: если значение не является целым
            числом или неположительно.
    """
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'ожидается целое число, получено {value!r}')
    if number <= 0:
        raise argparse.ArgumentTypeError('количество вхождений должно быть положительным целым числом')
    return number


def build_parser() -> argparse.ArgumentParser:
    """Создаёт аргументы командной строки утилиты.

    Returns:
        Настроенный парсер аргументов.
    """
    parser = argparse.ArgumentParser(
        description='Поиск подстрок в строке или файле (алгоритм Рабина-Карпа).',
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('-s', '--string', help='целевая строка для поиска')
    source.add_argument('-f', '--file', help='путь до файла, в котором производится поиск')
    parser.add_argument('-p', '--pattern', action='append', nargs='+', required=True,
                        help='одна или несколько искомых подстрок')
    parser.add_argument('--case-sensitive', action='store_true',
                        help='чувствительность к регистру (по умолчанию поиск без учёта регистра)')
    parser.add_argument('-m', '--method', choices=('first', 'last'), default='first',
                        help="направление поиска: 'first' — с начала, "
                             "'last' — с конца (по умолчанию first)")
    parser.add_argument('-k', '--count', type=_positive_count, default=None,
                        help='количество первых вхождений k '
                             '(должно быть положительным, по умолчанию без ограничения)')
    parser.add_argument('--max-lines', type=int, default=DEFAULT_MAX_LINES,
                        help=f'максимум выводимых строк текста (по умолчанию {DEFAULT_MAX_LINES})')
    parser.add_argument('--no-color', action='store_true',
                        help='вывод без цветового выделения найденных подстрок')
    return parser


def _line_matches(line: str, pattern: str, case_sensitivity: bool) -> list[int]:
    """Возвращает индексы вхождений подстроки в строке без логирования.

    Args:
        line: строка текста.
        pattern: искомая подстрока.
        case_sensitivity: флаг чувствительности к регистру.

    Returns:
        Список индексов начала вхождений.
    """
    haystack = line if case_sensitivity else line.lower()
    needle = pattern if case_sensitivity else pattern.lower()
    return rabin_karp(haystack, needle)


def highlight_line(line: str, patterns: Sequence[str], case_sensitivity: bool, color: bool) -> str:
    """Подсвечивает найденные подстроки в одной строке текста.

    Каждой подстроке соответствует свой цвет; пересекающиеся
    вхождения раскрашиваются по приоритету первой подстроки.

    Args:
        line: строка текста.
        patterns: искомые подстроки.
        case_sensitivity: флаг чувствительности к регистру.
        color: использовать ли цветовое выделение.

    Returns:
        Строка с вставленными escape-кодами цвета.
    """
    owners: list[Optional[int]] = [None] * len(line)
    for pattern_index, pattern in enumerate(patterns):
        for start in _line_matches(line, pattern, case_sensitivity):
            for position in range(start, min(start + len(pattern), len(line))):
                if owners[position] is None:
                    owners[position] = pattern_index

    parts: list[str] = []
    position = 0
    while position < len(line):
        owner = owners[position]
        end = position
        while end < len(line) and owners[end] == owner:
            end += 1
        chunk = line[position:end]
        if color and owner is not None:
            chunk = f'{COLORS[owner % len(COLORS)]}{chunk}{RESET}'
        parts.append(chunk)
        position = end
    return ''.join(parts)


def format_result(result: SearchResult) -> str:
    """Форматирует результат поиска для вывода в консоль.

    Args:
        result: результат функции :func:`search.search`.

    Returns:
        Читаемое представление найденных индексов.
    """
    if result is None:
        return 'Совпадений не найдено'
    if isinstance(result, dict):
        return '\n'.join(f'  {key!r}: {value if value is not None else "None"}'
                         for key, value in result.items())
    return f'  Индексы: {result}'


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Точка входа консольной утилиты.

    Args:
        argv: аргументы командной строки (по умолчанию ``sys.argv``).

    Returns:
        Код завершения процесса.
    """
    logging.basicConfig(level=logging.INFO, format='[лог] %(message)s')
    args = build_parser().parse_args(argv)

    patterns: list[str] = [item for group in args.pattern for item in group]
    if args.file:
        try:
            with open(args.file, encoding='utf-8') as file:
                text = file.read()
        except OSError as error:
            print(f'Ошибка чтения файла: {error}', file=sys.stderr)
            return 1
    else:
        text = args.string

    result = search(text, patterns, args.case_sensitive, args.method, args.count)

    print('Результат поиска:')
    print(format_result(result))

    lines = text.splitlines() or ['']
    printed = 0
    print('\nНайденные подстроки (выделены цветом):')
    for number, line in enumerate(lines, start=1):
        if printed >= max(args.max_lines, 0):
            print(f'  ... (вывод ограничен {args.max_lines} строками)')
            break
        if not any(_line_matches(line, pattern, args.case_sensitive)
                   for pattern in patterns):
            continue
        printed += 1
        highlighted = highlight_line(line, patterns, args.case_sensitive, not args.no_color)
        print(f'  {number:>4}: {highlighted}')

    if printed == 0:
        print('  Совпадений не найдено')

    return 0


if __name__ == '__main__':
    sys.exit(main())
