"""
Debugging tools for GB2Text.

Usage:
    python scripts/debug.py --rom <rom_path> --action <action>
    
Actions:
    dump-header   - Dump ROM header info
    scan-blocks   - Scan and list text blocks
    decode-block  - Decode specific text block
    trace          - Enable debug tracing
    inspect        - Inspect ROM structure
"""

import argparse
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rom import GameBoyROM
from core.scanner import TextScanner
from core.decoder import TextDecoder


def setup_debug_logging(level=logging.DEBUG):
    """Setup debug logging with detailed formatting."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger('GB2Text')


def dump_header(rom_path):
    """Dump ROM header information."""
    print(f"\n{'='*60}")
    print(f"ROM Header Dump: {rom_path}")
    print(f"{'='*60}\n")
    
    rom = GameBoyROM(rom_path)
    
    print(f"File: {os.path.basename(rom_path)}")
    print(f"Size: {rom.size} bytes ({rom.size / 1024:.1f} KB)")
    print(f"Header: {rom.header}")
    print(f"Type: {rom.type}")
    print(f"ROM Size: {rom.rom_size}")
    print(f"RAM Size: {ram_size if (ram_size := rom.ram_size) else 'N/A'}")
    print(f"Region: {rom.region}")
    print(f"Game Title: {rom.title}")
    print(f"CGB Flag: {rom.cgb_flag}")
    
    print(f"\nNintendo Logo Valid: {rom.validate_header()}")
    print(f"\nChecksum Valid: {hex(rom.calculate_checksum())}")


def scan_blocks(rom_path, limit=None):
    """Scan and list text blocks."""
    print(f"\n{'='*60}")
    print(f"Text Block Scanner: {rom_path}")
    print(f"{'='*60}\n")
    
    rom = GameBoyROM(rom_path)
    scanner = TextScanner(rom)
    
    print("Scanning for text blocks...")
    blocks = scanner.scan_text_blocks()
    
    if limit:
        blocks = blocks[:limit]
    
    print(f"\nFound {len(blocks)} text blocks:\n")
    
    for i, block in enumerate(blocks):
        print(f"[{i:04d}] Address: 0x{block.get('address', 0):06X} | "
              f"Size: {block.get('size', 0)} | "
              f"Type: {block.get('type', 'unknown')}")
        
        # Try to decode
        decoder = TextDecoder()
        try:
            text = decoder.decode_text(block.get('data', b''))
            if text:
                print(f"       Text: {text[:50]}{'...' if len(text) > 50 else ''}")
        except Exception as e:
            print(f"       Decode error: {e}")
        print()


def decode_block(rom_path, address):
    """Decode specific text block."""
    print(f"\n{'='*60}")
    print(f"Block Decoder: {rom_path}")
    print(f"Address: 0x{address:X}")
    print(f"{'='*60}\n")
    
    rom = GameBoyROM(rom_path)
    decoder = TextDecoder()
    
    # Read bytes from address
    data = rom.read_bytes(address, 256)
    
    print(f"Raw bytes: {data[:64].hex()}")
    print()
    
    text = decoder.decode_text(data)
    print(f"Decoded text: {text}")


def trace_mode(rom_path, enable=True):
    """Enable debug tracing mode."""
    logger = setup_debug_logging(logging.DEBUG if enable else logging.INFO)
    
    print(f"\n{'='*60}")
    print(f"Trace Mode: {'ENABLED' if enable else 'DISABLED'}")
    print(f"ROM: {rom_path}")
    print(f"{'='*60}\n")
    
    rom = GameBoyROM(rom_path)
    
    logger.debug("ROM object created")
    logger.debug(f"ROM size: {rom.size}")
    logger.debug(f"ROM type: {rom.type}")
    
    scanner = TextScanner(rom)
    logger.debug("Scanner created")
    
    logger.info("Starting scan...")
    blocks = scanner.scan_text_blocks()
    logger.info(f"Scan complete: {len(blocks)} blocks found")


def inspect_rom(rom_path):
    """Inspect ROM structure in detail."""
    print(f"\n{'='*60}")
    print(f"ROM Structure Inspector: {rom_path}")
    print(f"{'='*60}\n")
    
    rom = GameBoyROM(rom_path)
    
    # Header details
    print("=== ROM Header ===")
    header_fields = [
        ('Entry Point', rom.header[:4]),
        ('Nintendo Logo', rom.header[0x04:0x34]),
        ('Title', rom.header[0x34:0x4C]),
        ('Manufacturer Code', rom.header[0x4C:0x50] if len(rom.header) > 0x4C else None),
        ('CGB Flag', rom.header[0x43:0x44] if len(rom.header) > 0x43 else None),
        ('MBC Type', rom.header[0x46:0x47] if len(rom.header) > 0x46 else None),
        ('ROM Size', rom.header[0x48:0x49] if len(rom.header) > 0x48 else None),
        ('RAM Size', rom.header[0x49:0x4A] if len(rom.header) > 0x49 else None),
        ('Destination Code', rom.header[0x4A:0x4B] if len(rom.header) > 0x4A else None),
        ('ROM Version', rom.header[0x4C:0x4D] if len(rom.header) > 0x4C else None),
    ]
    
    for name, value in header_fields:
        if value:
            value_repr = value.hex() if isinstance(value, bytes) else str(value)
            print(f"  {name}: {value_repr}")
    
    print("\n=== ROM Structure ===")
    banks = rom.size // 0x4000
    print(f"Total Banks: {banks}")
    
    # MBC info
    print("\n=== MBC Information ===")
    if rom.mbc:
        print(f"  Type: {rom.mbc}")
        print(f"  RAM: {'Yes' if rom.has_ram else 'No'}")
        print(f"  Battery: {'Yes' if rom.has_battery else 'No'}")
    else:
        print("  Type: ROM Only (no MBC)")
    
    print("\n=== Memory Map ===")
    print("  0x0000-0x3FFF: Bank 0 (fixed)")
    print("  0x4000-0x7FFF: Bank N (switchable)")
    print("  0x8000-0x9FFF: Video RAM")
    print("  0xA000-0xBFFF: External RAM")
    print("  0xC000-0xCFFF: Work RAM (bank 0)")
    print("  0xD000-0xDFFF: Work RAM (bank N)")
    print("  0xFE00-0xFE9F: Sprite Attribute Table")
    print("  0xFF00-0xFF7F: I/O Registers")
    print("  0xFF80-0xFFFE: High RAM")
    print("  0xFFFF: Interrupt Enable")


def main():
    parser = argparse.ArgumentParser(
        description='GB2Text Debugging Tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--rom', '-r', required=True, help='ROM file path')
    parser.add_argument('--action', '-a', 
                        choices=['dump-header', 'scan-blocks', 'decode-block', 'trace', 'inspect'],
                        default='dump-header',
                        help='Debug action to perform')
    parser.add_argument('--address', '-d', type=lambda x: int(x, 0),
                        help='Address for decode-block action (hex or decimal)')
    parser.add_argument('--limit', '-l', type=int, default=None,
                        help='Limit number of results')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.rom):
        print(f"Error: ROM file not found: {args.rom}")
        sys.exit(1)
    
    if args.verbose:
        setup_debug_logging()
    
    try:
        if args.action == 'dump-header':
            dump_header(args.rom)
        elif args.action == 'scan-blocks':
            scan_blocks(args.rom, args.limit)
        elif args.action == 'decode-block':
            if args.address is None:
                print("Error: --address required for decode-block action")
                sys.exit(1)
            decode_block(args.rom, args.address)
        elif args.action == 'trace':
            trace_mode(args.rom)
        elif args.action == 'inspect':
            inspect_rom(args.rom)
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()