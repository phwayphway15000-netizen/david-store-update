import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { I18nProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth";
import StoreLayout from "@/components/store/StoreLayout";
import Home from "@/pages/store/Home";
import Catalog from "@/pages/store/Catalog";
import ProductDetail from "@/pages/store/ProductDetail";
import Support from "@/pages/store/Support";
import Policy from "@/pages/store/Policy";
import Track from "@/pages/store/Track";
import AdminLayout from "@/components/admin/AdminLayout";
import Login from "@/pages/admin/Login";
import Dashboard from "@/pages/admin/Dashboard";
import Products from "@/pages/admin/Products";
import ProductEditor from "@/pages/admin/ProductEditor";
import Taxonomy from "@/pages/admin/Taxonomy";
import Suppliers from "@/pages/admin/Suppliers";
import SupplierDetail from "@/pages/admin/SupplierDetail";
import Orders from "@/pages/admin/Orders";
import OrderDetail from "@/pages/admin/OrderDetail";
import Promotions from "@/pages/admin/Promotions";
import PaymentMethods from "@/pages/admin/PaymentMethods";
import Users from "@/pages/admin/Users";
import Settings from "@/pages/admin/Settings";
import Audit from "@/pages/admin/Audit";

function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<StoreLayout />}>
              <Route path="/" element={<Home />} />
              <Route path="/products" element={<Catalog />} />
              <Route path="/promotions" element={<Catalog promo />} />
              <Route path="/products/:slug" element={<ProductDetail />} />
              <Route path="/support" element={<Support />} />
              <Route path="/policies/:key" element={<Policy />} />
              <Route path="/track" element={<Track />} />
            </Route>
            <Route path="/admin/login" element={<Login />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="products" element={<Products />} />
              <Route path="products/:id" element={<ProductEditor />} />
              <Route path="catalog" element={<Taxonomy />} />
              <Route path="suppliers" element={<Suppliers />} />
              <Route path="suppliers/:id" element={<SupplierDetail />} />
              <Route path="orders" element={<Orders />} />
              <Route path="orders/:id" element={<OrderDetail />} />
              <Route path="promotions" element={<Promotions />} />
              <Route path="payment-methods" element={<PaymentMethods />} />
              <Route path="users" element={<Users />} />
              <Route path="settings" element={<Settings />} />
              <Route path="audit" element={<Audit />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-center" />
      </AuthProvider>
    </I18nProvider>
  );
}

export default App;
