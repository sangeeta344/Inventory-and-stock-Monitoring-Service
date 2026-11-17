/**
 * Smart Supermarket - POS Terminal & Billing Cart Controller
 */

let cart = [];
let defaultTaxRate = 5.0;

document.addEventListener('DOMContentLoaded', () => {
    // Read default tax rate from data attribute if available
    const taxInput = document.getElementById('tax-rate-input');
    if (taxInput) {
        defaultTaxRate = parseFloat(taxInput.value) || 5.0;
    }

    // Initialize Barcode Scanner Controller
    const scanner = new BarcodeScannerController('reader', onBarcodeDetected);
    window.posScanner = scanner;

    const btnStartCamera = document.getElementById('btn-start-camera');
    if (btnStartCamera) {
        btnStartCamera.addEventListener('click', () => {
            const scannerContainer = document.getElementById('scanner-modal-wrapper');
            scannerContainer.classList.toggle('d-none');
            if (!scannerContainer.classList.contains('d-none')) {
                scanner.startScanning("environment");
                btnStartCamera.innerHTML = '<i class="bi bi-camera-video-off me-1"></i> Close Camera';
                btnStartCamera.classList.replace('btn-outline-primary', 'btn-danger');
            } else {
                scanner.stopScanning();
                btnStartCamera.innerHTML = '<i class="bi bi-camera me-1"></i> Scan Product (Camera)';
                btnStartCamera.classList.replace('btn-danger', 'btn-outline-primary');
            }
        });
    }

    // Manual Barcode Input with Enter key
    const barcodeInput = document.getElementById('manual-barcode-input');
    if (barcodeInput) {
        barcodeInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const code = barcodeInput.value.trim();
                if (code) {
                    onBarcodeDetected(code);
                    barcodeInput.value = '';
                }
            }
        });
    }

    // Live Product Search Dropdown
    const searchInput = document.getElementById('live-search-input');
    const searchResultsDropdown = document.getElementById('search-results-dropdown');

    if (searchInput && searchResultsDropdown) {
        let debounceTimer = null;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            const query = searchInput.value.trim();
            if (query.length < 2) {
                searchResultsDropdown.classList.add('d-none');
                return;
            }

            debounceTimer = setTimeout(() => {
                fetch(`/api/billing/search-products?q=${encodeURIComponent(query)}`)
                    .then(res => res.json())
                    .then(data => {
                        searchResultsDropdown.innerHTML = '';
                        if (data.results && data.results.length > 0) {
                            data.results.forEach(prod => {
                                const item = document.createElement('a');
                                item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center cursor-pointer';
                                item.innerHTML = `
                                    <div>
                                        <div class="fw-semibold">${escapeHtml(prod.name)}</div>
                                        <small class="text-muted">Barcode: ${prod.barcode} | Stock: ${prod.current_stock} ${prod.unit_of_measure}</small>
                                    </div>
                                    <div class="text-end">
                                        <span class="badge bg-primary fs-6">$${prod.selling_price.toFixed(2)}</span>
                                    </div>
                                `;
                                item.addEventListener('click', () => {
                                    addProductToCart(prod);
                                    searchInput.value = '';
                                    searchResultsDropdown.classList.add('d-none');
                                });
                                searchResultsDropdown.appendChild(item);
                            });
                            searchResultsDropdown.classList.remove('d-none');
                        } else {
                            searchResultsDropdown.innerHTML = '<div class="list-group-item text-muted text-center py-2">No matching products found</div>';
                            searchResultsDropdown.classList.remove('d-none');
                        }
                    });
            }, 250);
        });

        // Hide search on outside click
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !searchResultsDropdown.contains(e.target)) {
                searchResultsDropdown.classList.add('d-none');
            }
        });
    }

    // Discount & Tax rate changes
    const discountInput = document.getElementById('discount-input');
    if (discountInput) {
        discountInput.addEventListener('input', recalculateTotals);
    }
    if (taxInput) {
        taxInput.addEventListener('input', recalculateTotals);
    }

    // Checkout button
    const btnCheckout = document.getElementById('btn-checkout');
    if (btnCheckout) {
        btnCheckout.addEventListener('click', processCheckout);
    }

    // Clear cart button
    const btnClearCart = document.getElementById('btn-clear-cart');
    if (btnClearCart) {
        btnClearCart.addEventListener('click', () => {
            if (cart.length > 0 && confirm('Clear all items from current cart?')) {
                cart = [];
                renderCart();
            }
        });
    }
});

// Callback when barcode is detected (from camera or manual barcode scanner gun)
function onBarcodeDetected(barcode) {
    showToast(`Looking up barcode: ${barcode}...`, 'info');

    fetch(`/api/billing/product-lookup/${encodeURIComponent(barcode)}`)
        .then(res => res.json())
        .then(data => {
            if (data.success && data.product) {
                addProductToCart(data.product);
                showToast(`Added ${data.product.name} to cart`, 'success');
            } else {
                showToast(data.message || `Product not found for barcode ${barcode}`, 'danger');
            }
        })
        .catch(err => {
            console.error("Barcode lookup error:", err);
            showToast("Failed to lookup barcode from server.", 'danger');
        });
}

// Add or increment item in cart
function addProductToCart(product, qtyToAdd = 1) {
    const existing = cart.find(item => item.product_id === product.id);

    if (existing) {
        const newQty = existing.quantity + qtyToAdd;
        if (newQty > product.current_stock) {
            showToast(`Cannot add more. Available stock is ${product.current_stock} ${product.unit_of_measure}`, 'warning');
            return;
        }
        existing.quantity = newQty;
        existing.subtotal = existing.quantity * existing.selling_price;
    } else {
        if (product.current_stock < qtyToAdd) {
            showToast(`Product is out of stock (${product.current_stock} available)`, 'danger');
            return;
        }
        cart.push({
            product_id: product.id,
            name: product.name,
            barcode: product.barcode,
            selling_price: parseFloat(product.selling_price),
            current_stock: product.current_stock,
            unit_of_measure: product.unit_of_measure || 'pcs',
            quantity: qtyToAdd,
            subtotal: qtyToAdd * parseFloat(product.selling_price)
        });
    }

    renderCart();
}

// Render Cart Items
function renderCart() {
    const cartContainer = document.getElementById('cart-items-container');
    const emptyState = document.getElementById('cart-empty-state');
    const cartCountEl = document.getElementById('cart-item-count');

    if (!cartContainer) return;

    if (cart.length === 0) {
        cartContainer.innerHTML = '';
        if (emptyState) emptyState.classList.remove('d-none');
        if (cartCountEl) cartCountEl.innerText = '0 items';
        recalculateTotals();
        return;
    }

    if (emptyState) emptyState.classList.add('d-none');
    if (cartCountEl) cartCountEl.innerText = `${cart.reduce((sum, item) => sum + item.quantity, 0)} items`;

    cartContainer.innerHTML = '';

    cart.forEach(item => {
        const row = document.createElement('div');
        row.className = 'cart-item-row';
        row.innerHTML = `
            <div style="flex: 1 1 50%; min-width: 0;" class="pe-2">
                <div class="fw-semibold text-truncate" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
                <div class="text-muted small">$${item.selling_price.toFixed(2)} / ${item.unit_of_measure}</div>
            </div>
            <div class="d-flex align-items-center gap-1 me-2">
                <button class="btn btn-sm btn-outline-secondary px-2 py-0" onclick="changeQuantity(${item.product_id}, -1)">-</button>
                <input type="number" class="form-control form-control-sm text-center px-1" style="width: 48px;" 
                       value="${item.quantity}" min="1" max="${item.current_stock}" 
                       onchange="setQuantityDirect(${item.product_id}, this.value)">
                <button class="btn btn-sm btn-outline-secondary px-2 py-0" onclick="changeQuantity(${item.product_id}, 1)">+</button>
            </div>
            <div class="text-end fw-bold" style="width: 65px;">
                $${item.subtotal.toFixed(2)}
            </div>
            <button class="btn btn-link text-danger p-0 ms-2" onclick="removeCartItem(${item.product_id})" title="Remove">
                <i class="bi bi-trash"></i>
            </button>
        `;
        cartContainer.appendChild(row);
    });

    recalculateTotals();
}

function changeQuantity(productId, delta) {
    const item = cart.find(i => i.product_id === productId);
    if (!item) return;

    const newQty = item.quantity + delta;
    if (newQty <= 0) {
        removeCartItem(productId);
        return;
    }

    if (newQty > item.current_stock) {
        showToast(`Cannot exceed available stock of ${item.current_stock}`, 'warning');
        return;
    }

    item.quantity = newQty;
    item.subtotal = item.quantity * item.selling_price;
    renderCart();
}

function setQuantityDirect(productId, val) {
    const item = cart.find(i => i.product_id === productId);
    if (!item) return;

    let qty = parseInt(val) || 1;
    if (qty <= 0) qty = 1;
    if (qty > item.current_stock) {
        showToast(`Max available stock is ${item.current_stock}`, 'warning');
        qty = item.current_stock;
    }

    item.quantity = qty;
    item.subtotal = item.quantity * item.selling_price;
    renderCart();
}

function removeCartItem(productId) {
    cart = cart.filter(item => item.product_id !== productId);
    renderCart();
}

function recalculateTotals() {
    const subtotal = cart.reduce((acc, item) => acc + item.subtotal, 0.0);
    const discountEl = document.getElementById('discount-input');
    const taxEl = document.getElementById('tax-rate-input');

    const discount = Math.max(0, parseFloat(discountEl ? discountEl.value : 0) || 0);
    const taxRate = Math.max(0, parseFloat(taxEl ? taxEl.value : 5.0) || 0);

    const discountedSubtotal = Math.max(0, subtotal - discount);
    const tax = discountedSubtotal * (taxRate / 100.0);
    const finalAmount = discountedSubtotal + tax;

    const subtotalEl = document.getElementById('cart-subtotal');
    const taxAmountEl = document.getElementById('cart-tax');
    const finalTotalEl = document.getElementById('cart-final-total');
    const payAmountBtn = document.getElementById('btn-pay-amount');

    if (subtotalEl) subtotalEl.innerText = `$${subtotal.toFixed(2)}`;
    if (taxAmountEl) taxAmountEl.innerText = `$${tax.toFixed(2)}`;
    if (finalTotalEl) finalTotalEl.innerText = `$${finalAmount.toFixed(2)}`;
    if (payAmountBtn) payAmountBtn.innerText = `$${finalAmount.toFixed(2)}`;
}

// Checkout and Save to MySQL
function processCheckout() {
    if (cart.length === 0) {
        showToast('Cart is empty! Add products before checking out.', 'warning');
        return;
    }

    const customerNameInput = document.getElementById('customer-name-input');
    const customerPhoneInput = document.getElementById('customer-phone-input');
    const paymentMethodInput = document.querySelector('input[name="payment_method"]:checked');
    const discountInput = document.getElementById('discount-input');
    const taxRateInput = document.getElementById('tax-rate-input');

    const payload = {
        cart: cart,
        customer_name: customerNameInput ? customerNameInput.value.trim() : 'Walk-in Customer',
        customer_phone: customerPhoneInput ? customerPhoneInput.value.trim() : '',
        payment_method: paymentMethodInput ? paymentMethodInput.value : 'CASH',
        discount_amount: parseFloat(discountInput ? discountInput.value : 0) || 0.0,
        tax_rate: parseFloat(taxRateInput ? taxRateInput.value : 5.0) || 5.0
    };

    const btnCheckout = document.getElementById('btn-checkout');
    btnCheckout.disabled = true;
    btnCheckout.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';

    fetch('/api/billing/checkout', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(async res => {
        const contentType = res.headers.get('content-type') || '';
        let data = null;
        if (contentType.includes('application/json')) {
            data = await res.json();
        }

        if (!res.ok) {
            if (res.status === 401 || res.url.includes('/login')) {
                throw new Error("Your session expired. Please refresh the page and log in.");
            }
            const msg = data && data.message ? data.message : `Server error (${res.status})`;
            throw new Error(msg);
        }
        return data;
    })
    .then(data => {
        btnCheckout.disabled = false;
        btnCheckout.innerHTML = '<i class="bi bi-check-circle me-1"></i> Confirm & Generate Bill';

        if (data && data.success) {
            cart = [];
            showToast(`Bill generated: ${data.invoice_number}`, 'success');
            // Redirect to digital invoice page
            window.location.href = data.redirect_url;
        } else {
            const err = data && data.message ? data.message : 'Checkout failed.';
            showToast(err, 'danger');
            alert(`Checkout Error: ${err}`);
        }
    })
    .catch(err => {
        btnCheckout.disabled = false;
        btnCheckout.innerHTML = '<i class="bi bi-check-circle me-1"></i> Confirm & Generate Bill';
        console.error("Checkout error:", err);
        showToast(err.message || 'Server connection error during checkout.', 'danger');
    });
}

// Toast alert notification helper
function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-bg-${type} border-0 show shadow`;
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body fw-medium">${escapeHtml(message)}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    container.appendChild(toastEl);
    setTimeout(() => {
        toastEl.remove();
    }, 3200);
}

function escapeHtml(text) {
    if (!text) return '';
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
