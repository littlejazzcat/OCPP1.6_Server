"""页面路由 —— 渲染 Jinja2 模板（原生方式，绕过 Starlette Jinja2Templates 兼容性问题）"""

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from .app import app
from models.database import async_session
from services import cp_service, transaction_service, auth_service

# 直接使用 Jinja2 原生 Environment，不用 Starlette 的 Jinja2Templates 包装
templates_dir = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)


def render(name: str, context: dict) -> HTMLResponse:
    """渲染模板并返回 HTMLResponse"""
    template = jinja_env.get_template(name)
    # 将 request 注入到 url_for 函数中
    html = template.render(context)
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """仪表盘首页"""
    async with async_session() as db:
        cps = await cp_service.list_all(db)
        txs = await transaction_service.list_transactions(db, limit=10)

    return render("dashboard.html", {
        "request": request,
        "charge_points": cps,
        "transactions": txs,
        "online_count": sum(1 for cp in cps if cp.online),
        "total_count": len(cps),
    })


@app.get("/charge-points", response_class=HTMLResponse)
async def charge_point_list(request: Request):
    """充电桩列表"""
    async with async_session() as db:
        cps = await cp_service.list_all(db)

    return render("charge_points.html", {
        "request": request,
        "charge_points": cps,
    })


@app.get("/charge-points/{charge_box_id}", response_class=HTMLResponse)
async def charge_point_detail(request: Request, charge_box_id: str):
    """充电桩详情"""
    async with async_session() as db:
        cp = await cp_service.get_by_charge_box_id(db, charge_box_id)
        if cp is None:
            return HTMLResponse("Charge point not found", status_code=404)
        connectors = await cp_service.get_connectors(db, cp.id)
        txs = await transaction_service.list_transactions(db, charge_point_id=cp.id, limit=30)

    return render("charge_point_detail.html", {
        "request": request,
        "cp": cp,
        "connectors": connectors,
        "transactions": txs,
    })


@app.get("/transactions", response_class=HTMLResponse)
async def transaction_list(request: Request):
    """交易记录"""
    async with async_session() as db:
        txs = await transaction_service.list_transactions(db, limit=100)

    return render("transactions.html", {
        "request": request,
        "transactions": txs,
    })


@app.get("/tags", response_class=HTMLResponse)
async def tag_list(request: Request):
    """OCPP 标签管理"""
    async with async_session() as db:
        tags = await auth_service.list_tags(db)

    return render("tags.html", {
        "request": request,
        "tags": tags,
    })


@app.get("/operations", response_class=HTMLResponse)
async def operations(request: Request):
    """远程操作面板"""
    async with async_session() as db:
        cps = await cp_service.list_all(db)

    return render("operations.html", {
        "request": request,
        "charge_points": cps,
    })
