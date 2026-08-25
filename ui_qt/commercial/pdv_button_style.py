"""Folha exclusivamente visual para botões do PDV e seus diálogos."""

PDV_BUTTON_STYLE = """
QPushButton {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #626a72,stop:.45 #41474d,stop:1 #272c31);
 color:#f6f7f8;border:1px solid #7a838b;border-radius:7px;
 min-height:36px;padding:0 14px;font-weight:700;
}
QPushButton:hover {
 border-color:#a8b0b7;
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #737c84,stop:1 #343a40);
}
QPushButton:focus { border:2px solid #73c7dc; }
QPushButton:disabled { color:#7f878e;background:#25292d;border-color:#3c4248; }
QPushButton#primary {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #567984,stop:1 #294852);
 border-color:#73c7dc;
}
QPushButton#checkout {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #52705e,stop:1 #294535);
 border-color:#799d85;min-height:50px;font-size:15px;
}
QPushButton#close {
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #a13b42,stop:1 #53191e);
 border-color:#d65b63;
}
QPushButton#inactive { color:#cbd0d4;background:#30353a;border-color:#596169; }
"""

PDV_DESTRUCTIVE_BUTTON_STYLE = """
background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #a13b42,stop:1 #53191e);
color:#ffffff;border:1px solid #d65b63;border-radius:7px;min-height:36px;
padding:0 14px;font-weight:700;
"""

PDV_BUDGET_ACTIVE_STYLE = """
background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #786b4d,stop:1 #443b25);
color:#ffffff;border:1px solid #b8a064;border-radius:7px;font-weight:700;padding:9px;
"""
