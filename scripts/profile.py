"""
Profiling tools for GB2Text.

Usage:
    python scripts/profile.py --module <module_name> --input <input_file>
    
Modules:
    rom-loading   - Profile ROM loading
    scanning      - Profile text scanning
    decoding      - Profile text decoding
    encoding      - Profile text encoding
    full-workflow - Profile full extraction workflow
"""

import argparse
import cProfile
import pstats
import io
import sys
import os
import time
from contextlib import contextmanager

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@contextmanager
def timer(name):
    """Context manager for timing operations."""
    start = time.perf_counter()
    yield
    end = time.perf_counter()
    print(f"[TIMER] {name}: {(end - start) * 1000:.2f}ms")


@contextmanager
def memory_tracker():
    """Context manager for memory tracking."""
    import tracemalloc
    tracemalloc.start()
    yield
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"[MEMORY] Current: {current / 1024:.1f}KB, Peak: {peak / 1024:.1f}KB")
    return peak


def profile_function(func, *args, **kwargs):
    """Profile a function using cProfile."""
    profiler = cProfile.Profile()
    profiler.enable()
    
    result = func(*args, **kwargs)
    
    profiler.disable()
    
    # Output stats
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.sort_stats('cumulative')
    ps.print_stats(20)
    
    return result, s.getvalue()


def profile_module_rom_loading(rom_path):
    """Profile ROM loading operation."""
    print(f"\n{'='*60}")
    print(f"Profiling: ROM Loading")
    print(f"ROM: {rom_path}")
    print(f"{'='*60}\n")
    
    from core.rom import GameBoyROM
    
    # Profile loading
    result, stats = profile_function(GameBoyROM, rom_path)
    print(stats)
    
    with memory_tracker():
        pass
    
    return result


def profile_module_scanning(rom_path):
    """Profile text scanning operation."""
    print(f"\n{'='*60}")
    print(f"Profiling: Text Scanning")
    print(f"ROM: {rom_path}")
    print(f"{'='*60}\n")
    
    from core.rom import GameBoyROM
    from core.scanner import TextScanner
    
    rom = GameBoyROM(rom_path)
    
    with timer("ROM Loading"):
        pass  # Already loaded
    
    scanner = TextScanner(rom)
    
    result, stats = profile_function(scanner.scan_text_blocks)
    print(stats)
    
    print(f"\n[RESULT] Found {len(result)} text blocks")
    
    with memory_tracker():
        pass
    
    return result


def profile_module_decoding(rom_path, limit=100):
    """Profile text decoding operation."""
    print(f"\n{'='*60}")
    print(f"Profiling: Text Decoding")
    print(f"ROM: {rom_path}")
    print(f"{'='*60}\n")
    
    from core.rom import GameBoyROM
    from core.scanner import TextScanner
    from core.decoder import TextDecoder
    
    rom = GameBoyROM(rom_path)
    scanner = TextScanner(rom)
    decoder = TextDecoder()
    
    blocks = scanner.scan_text_blocks()[:limit]
    
    def decode_blocks():
        decoded = []
        for block in blocks:
            text = decoder.decode_text(block.get('data', b''))
            decoded.append(text)
        return decoded
    
    result, stats = profile_function(decode_blocks)
    print(stats)
    
    print(f"\n[RESULT] Decoded {len(result)} text blocks")
    
    with memory_tracker():
        pass
    
    return result


def profile_module_encoding(text_samples):
    """Profile text encoding operation."""
    print(f"\n{'='*60}")
    print(f"Profiling: Text Encoding")
    print(f"Samples: {len(text_samples)}")
    print(f"{'='*60}\n")
    
    from core.encoding import GB2TextEncoder
    
    encoder = GB2TextEncoder()
    
    def encode_texts():
        encoded = []
        for text in text_samples:
            data = encoder.encode_text(text)
            encoded.append(data)
        return encoded
    
    result, stats = profile_function(encode_texts)
    print(stats)
    
    print(f"\n[RESULT] Encoded {len(result)} texts")
    
    with memory_tracker():
        pass
    
    return result


def profile_full_workflow(rom_path, iterations=1):
    """Profile full extraction workflow."""
    print(f"\n{'='*60}")
    print(f"Profiling: Full Workflow")
    print(f"ROM: {rom_path}")
    print(f"Iterations: {iterations}")
    print(f"{'='*60}\n")
    
    from core.rom import GameBoyROM
    from core.scanner import TextScanner
    from core.decoder import TextDecoder
    from core.tmx import TMXExporter
    import tempfile
    
    def full_workflow():
        rom = GameBoyROM(rom_path)
        scanner = TextScanner(rom)
        blocks = scanner.scan_text_blocks()
        
        decoder = TextDecoder()
        decoded = []
        for block in blocks:
            text = decoder.decode_text(block.get('data', b''))
            if text:
                decoded.append({
                    'id': len(decoded) + 1,
                    'source': text,
                    'target': '',
                })
        
        return len(decoded)
    
    with memory_tracker():
        pass
    
    # Run workflow
    with timer("Full Workflow"):
        for i in range(iterations):
            count = full_workflow()
            print(f"[ITERATION {i+1}] Found {count} texts")
    
    # Profile the workflow
    result, stats = profile_function(full_workflow)
    print(stats)
    
    return result


def generate_benchmark_report(rom_path, output_file=None):
    """Generate comprehensive benchmark report."""
    print(f"\n{'='*60}")
    print(f"Generating Benchmark Report")
    print(f"ROM: {rom_path}")
    print(f"{'='*60}\n")
    
    from core.rom import GameBoyROM
    from core.scanner import TextScanner
    
    results = {}
    
    # ROM Loading
    with timer("ROM Loading"):
        rom = GameBoyROM(rom_path)
    results['rom_loading'] = {'status': 'success', 'size': rom.size}
    
    # Scanning
    with timer("Text Scanning"):
        scanner = TextScanner(rom)
        blocks = scanner.scan_text_blocks()
    results['scanning'] = {'status': 'success', 'blocks_found': len(blocks)}
    
    # Memory
    import tracemalloc
    tracemalloc.start()
    rom2 = GameBoyROM(rom_path)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    results['memory'] = {
        'current_kb': current / 1024,
        'peak_kb': peak / 1024,
    }
    
    # Print report
    print("\n" + "="*60)
    print("BENCHMARK REPORT")
    print("="*60)
    
    for module, data in results.items():
        print(f"\n{module.upper()}:")
        for key, value in data.items():
            print(f"  {key}: {value}")
    
    if output_file:
        import json
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nReport saved to: {output_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='GB2Text Profiling Tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--module', '-m',
                        choices=['rom-loading', 'scanning', 'decoding', 'encoding', 'full-workflow', 'benchmark'],
                        default='rom-loading',
                        help='Module to profile')
    parser.add_argument('--input', '-i', help='Input ROM file path')
    parser.add_argument('--output', '-o', help='Output file for benchmark report')
    parser.add_argument('--iterations', '-n', type=int, default=1,
                        help='Number of iterations for benchmark')
    parser.add_argument('--limit', '-l', type=int, default=100,
                        help='Limit for decoding operations')
    
    args = parser.parse_args()
    
    if args.module in ['rom-loading', 'scanning', 'decoding', 'full-workflow', 'benchmark']:
        if not args.input:
            print("Error: --input required for this module")
            sys.exit(1)
        
        if not os.path.exists(args.input):
            print(f"Error: Input file not found: {args.input}")
            sys.exit(1)
    
    try:
        if args.module == 'rom-loading':
            profile_module_rom_loading(args.input)
        elif args.module == 'scanning':
            profile_module_scanning(args.input)
        elif args.module == 'decoding':
            profile_module_decoding(args.input, args.limit)
        elif args.module == 'encoding':
            # Generate sample texts
            sample_texts = [f"Test text {i}" for i in range(100)]
            profile_module_encoding(sample_texts)
        elif args.module == 'full-workflow':
            profile_full_workflow(args.input, args.iterations)
        elif args.module == 'benchmark':
            generate_benchmark_report(args.input, args.output)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()