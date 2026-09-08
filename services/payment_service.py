from payments.klikqris import KlikQRIS
client=KlikQRIS()
async def create(order,description): return await client.create(order['order_id'],order['amount'],description)
async def status(order_id): return await client.status(order_id)
