"""
FFTA LZSS decompressor from MyGuyz/Final-Fantasy-Tactics-Advance
Reference implementation — 8 command types, bit-packed format.
Source: https://github.com/MyGuyz/Final-Fantasy-Tactics-Advance/blob/main/tools/lzss01.py
"""
import sys

def lzss_decompress_ex(data, src_off, max_out=1<<21, hard_cap_iters=1<<22):
    if src_off+4 > len(data):
        return None
    retlen = (data[src_off]<<24) | (data[src_off+1]<<16) | (data[src_off+2]<<8) | data[src_off+3]
    if retlen == 0 or retlen > max_out:
        return None
    dest = bytearray(retlen)
    xin = src_off + 4
    xout = 0
    dl = len(data)
    iters = 0
    while xout < retlen:
        iters += 1
        if iters > hard_cap_iters:
            return None
        if xin >= dl:
            return None
        b = data[xin]
        if b & 0x80:
            if xin+1 >= dl: return None
            tmp = xout - ((b & 0x07) << 8) - data[xin+1] - 1
            cnt = ((b >> 3) & 0x0F) + 3
            if tmp < 0: return None
            for _ in range(cnt):
                if xout >= retlen: break
                dest[xout] = dest[tmp]
                xout += 1
                tmp += 1
            xin += 1
        elif b & 0x40:
            cnt = (b & 0x3F) + 1
            for _ in range(cnt):
                xin += 1
                if xin >= dl or xout >= retlen: return None
                dest[xout] = data[xin]
                xout += 1
        elif b & 0x20:
            cnt = (b & 0x1F) + 2
            for _ in range(cnt):
                if xout >= retlen: break
                dest[xout] = 0x00
                xout += 1
        elif b & 0x10:
            if xin+2 >= dl: return None
            j = ((data[xin+1] & 0x3F) << 8) | data[xin+2]
            tmp = xout - j - 1
            if tmp < 0: tmp = 0
            cnt = (((data[xin+1] >> 2) & 0x30) | (b & 0x0F)) + 4
            for _ in range(cnt):
                if xout >= retlen: break
                dest[xout] = dest[tmp]
                tmp += 1
                xout += 1
            xin += 2
        elif b == 0x01:
            if xin+1 >= dl: return None
            cnt = data[xin+1] + 3
            for _ in range(cnt):
                if xout >= retlen: break
                dest[xout] = 0xFF
                xout += 1
            xin += 1
        elif b == 0x02:
            if xin+1 >= dl: return None
            cnt = data[xin+1] + 3
            for _ in range(cnt):
                if xout >= retlen: break
                dest[xout] = 0x00
                xout += 1
            xin += 1
        elif b == 0x00:
            if xin+3 >= dl: return None
            j = data[xin+3] | (data[xin+2] << 8)
            tmp = xout - j - 1
            if tmp < 0: tmp = 0
            cnt = data[xin+1] + 5
            for _ in range(cnt):
                if xout >= retlen: break
                dest[xout] = dest[tmp]
                xout += 1
                tmp += 1
            xin += 3
        else:
            return None
        xin += 1
    return bytes(dest), (xin - src_off)


def lzss_decompress(data, src_off, max_out=1<<21, hard_cap_iters=1<<22):
    r = lzss_decompress_ex(data, src_off, max_out, hard_cap_iters)
    if r is None:
        return None
    return r[0]
