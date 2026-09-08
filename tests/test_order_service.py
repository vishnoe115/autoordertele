from services.order_service import rupiah,new_order_id
def test_rupiah(): assert rupiah(125000)=='Rp125.000'
def test_order_id(): assert new_order_id(123).startswith('INV-')
