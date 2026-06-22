"""
fixtures.py
-----------
Kumpulan data HTML contoh (mock) yang merepresentasikan struktur asli
halaman https://fashion-studio.dicoding.dev/. Digunakan oleh
test_extract.py agar pengujian tidak perlu melakukan request ke
internet sungguhan.
"""

SAMPLE_PAGE_HTML = """
<!DOCTYPE html><html lang="en"><head><title>Fashion Studio</title></head>
<body>
<main class="container">
<div class="collection-grid" id="collectionList">
    <div class="collection-card">
        <div style="position: relative;">
            <img src="https://picsum.photos/280/350?random=1" class="collection-image" alt="Unknown Product">
        </div>
        <div class="product-details">
            <h3 class="product-title">Unknown Product</h3>
            <div class="price-container"><span class="price">$100.00</span></div>
            <p style="font-size: 14px; color: #777;">Rating: \u2b50 Invalid Rating / 5</p>
            <p style="font-size: 14px; color: #777;">5 Colors</p>
            <p style="font-size: 14px; color: #777;">Size: M</p>
            <p style="font-size: 14px; color: #777;">Gender: Men</p>
        </div>
    </div>
    <div class="collection-card">
        <div style="position: relative;">
            <img src="https://picsum.photos/280/350?random=2" class="collection-image" alt="T-shirt 2">
        </div>
        <div class="product-details">
            <h3 class="product-title">T-shirt 2</h3>
            <div class="price-container"><span class="price">$102.15</span></div>
            <p style="font-size: 14px; color: #777;">Rating: \u2b50 3.9 / 5</p>
            <p style="font-size: 14px; color: #777;">3 Colors</p>
            <p style="font-size: 14px; color: #777;">Size: M</p>
            <p style="font-size: 14px; color: #777;">Gender: Women</p>
        </div>
    </div>
    <div class="collection-card">
        <div style="position: relative;">
            <img src="https://picsum.photos/280/350?random=16" class="collection-image" alt="Pants 16">
        </div>
        <div class="product-details">
            <h3 class="product-title">Pants 16</h3>
            <p class="price">Price Unavailable</p>
            <p style="font-size: 14px; color: #777;">Rating: Not Rated</p>
            <p style="font-size: 14px; color: #777;">8 Colors</p>
            <p style="font-size: 14px; color: #777;">Size: S</p>
            <p style="font-size: 14px; color: #777;">Gender: Men</p>
        </div>
    </div>
    <div class="collection-card">
        <div style="position: relative;">
            <img src="https://picsum.photos/280/350?random=3" class="collection-image" alt="Hoodie 3">
        </div>
        <div class="product-details">
            <h3 class="product-title">Hoodie 3</h3>
            <div class="price-container"><span class="price">$496.88</span></div>
            <p style="font-size: 14px; color: #777;">Rating: \u2b50 4.8 / 5</p>
            <p style="font-size: 14px; color: #777;">3 Colors</p>
            <p style="font-size: 14px; color: #777;">Size: L</p>
            <p style="font-size: 14px; color: #777;">Gender: Unisex</p>
        </div>
    </div>
</div>
</main>
</body></html>
"""

EMPTY_PAGE_HTML = """
<!DOCTYPE html><html><body>
<div class="collection-grid" id="collectionList"></div>
</body></html>
"""
