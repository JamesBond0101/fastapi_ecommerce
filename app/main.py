import uuid
from fastapi import FastAPI, Request, Response
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from app.routers import categories, products, users, reviews, cart, orders
from loguru import logger


app = FastAPI(
    title="Ecommerce App",
    version="0.1.0",
)
app.mount("/media", StaticFiles(directory="media"), name="media")


logger.add("info.log", format="Log: [{extra[log_id]}:{time} - {level} - {message}]", level="INFO", enqueue=True)
@app.middleware("http")
async def log_middleware(request: Request, call_next) -> Response:
    log_id = str(uuid.uuid4())
    with logger.contextualize(log_id=log_id):
        try:
            response = await call_next(request)
            if response.status_code in [401, 402, 403, 404]:
                logger.warning(f"Request to {request.url.path} failed")
            else:
                logger.info('Successfully accessed ' + request.url.path)
        except Exception as ex:
            logger.error(f"Request to {request.url.path} failed: {ex}")
            response = JSONResponse(content={"success": False}, status_code=500)
        return response


app.include_router(categories.router)
app.include_router(products.router)
app.include_router(users.router)
app.include_router(reviews.router)
app.include_router(cart.router)
app.include_router(orders.router)


@app.get("/")
async def root() -> dict:
    return {"message": "Добро пожаловать в API интернет-магазина!"}