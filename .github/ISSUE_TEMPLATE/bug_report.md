---
name: Bug report
about: Create a report that will help us improve the program
title: "[Bug]"
labels: bug
assignees: Far-g-Us

---

### 🐛 **Error description**
Clearly describe what the problem is

### 🕹️ **Steps to reproduce**
1. Game: `[Game name].gb` [gb/gbc/gba] (specify the CRC32 or SHA-1 hash)
2. ROM version: `[USA/EU/JPN]`
3. Command: `[The full command you entered]`
4. Expected result: `[...]`
5. Actual result: `[...]`

### 📄 **Execution log**
```plaintext
[Insert the program log text here]
```

(Run the script with the --verbose flag for a detailed log)

🧩 Configuration <br>
-Software version: gb2text vX.X.X <br>
-OS: Windows 11 / Ubuntu 22.04 / macOS 14 <br>
-Launch options: [Your flags and arguments] <br>
-Related files: <br>
-config.ini (if used) <br>
-Character table: [charmap.json/custom_map.txt] <br>

💡 Suggestions <br>
Do you have any ideas about what could have caused the problem? <br>
🖼️ Visual evidence <br>
*Screenshot* <br>

🚧 Additional context <br> 
-First occurrence: [Date/version] <br>
-Frequency: Always/Sometimes/Once <br>
Related issues: #123, #456 <br>


---

### 📂 How to add to the repository:
1. Create a file in the `.github/ISSUE_TEMPLATE/` directory
2. Name it `BUG_REPORT.md`
3. Paste the contents above
4. Add to `README.md`:

## 🐞 Bug reports

If you find any issues:
1. Check the [open issues](https://github.com/Far-g-Us/gb2text/issues)
2. Create a new report using the [template](https://github.com/Far-g-Us/gb2text/issues/new?template=BUG_REPORT.md)
