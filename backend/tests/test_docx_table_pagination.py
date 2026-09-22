from xml.etree import ElementTree as ET

from app.services.work_tasks.openxml import _docx_table

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"


def table(rows, **kwargs):
    return ET.fromstring(f'<root xmlns:w="{NS["w"]}">{_docx_table(rows, **kwargs)}</root>')[0]


def test_numbered_table_preserves_two_digit_index_and_repeats_intact_header():
    root = table([["序号", "内容 / 证据 / 验证动作"], *[[str(i), "可换行的中文说明" * 20] for i in range(1, 81)]])
    widths = [int(col.attrib[W + "w"]) for col in root.findall("w:tblGrid/w:gridCol", NS)]
    assert widths == [960, 8706]
    assert root.find("w:tblPr/w:tblLayout", NS).attrib[W + "type"] == "fixed"
    rows = root.findall("w:tr", NS)
    for index, row in enumerate(rows):
        assert row.find("w:trPr/w:cantSplit", NS) is not None
        assert (row.find("w:trPr/w:tblHeader", NS) is not None) == (index == 0)
        first, content = row.findall("w:tc", NS)
        assert first.find("w:tcPr/w:noWrap", NS) is not None
        assert content.find("w:tcPr/w:noWrap", NS) is None
        assert (content.find("w:p/w:pPr/w:keepNext", NS) is not None) == (index == 0)
    assert rows[10].find("w:tc/w:p/w:r/w:t", NS).text == "10"
    assert root.findall(".//w:trHeight", NS) == []  # Never clip a row to a fixed height.


def test_descriptive_tables_reserve_label_space_and_escape_content():
    root = table([["项目", "说明"], ["<项目&名称>", "内容"]], accent_first_row=False)
    assert [int(col.attrib[W + "w"]) for col in root.findall("w:tblGrid/w:gridCol", NS)] == [2400, 7266]
    assert root.findall(".//w:tblHeader", NS) == []
    assert root.findall(".//w:noWrap", NS) == []
    assert root.findall("w:tr", NS)[1].find("w:tc/w:p/w:r/w:t", NS).text == "<项目&名称>"
