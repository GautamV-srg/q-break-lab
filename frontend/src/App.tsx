import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import SymmetricTest from "./pages/SymmetricTest";
import PublicKeyTest from "./pages/PublicKeyTest";
import Evaluation from "./pages/Evaluation";
import Mosca from "./pages/Mosca";
import Readiness from "./pages/Readiness";
import About from "./pages/About";
import NotFound from "./pages/NotFound";

const TITLES: Record<string, string> = {
  "/": "Q-Break · Quantum red-team engine",
  "/test/symmetric": "Symmetric breach test · Q-Break",
  "/test/public-key": "Public-key breach test · Q-Break",
  "/evaluation": "Evaluation · Q-Break",
  "/mosca": "Mosca risk calculator · Q-Break",
  "/readiness": "Quantum Readiness Check · Q-Break",
  "/about": "How Q-Break works · Q-Break",
};

export default function App() {
  const { pathname } = useLocation();
  useEffect(() => {
    document.title = TITLES[pathname] ?? "Q-Break";
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/test/symmetric" element={<SymmetricTest />} />
        <Route path="/test/public-key" element={<PublicKeyTest />} />
        <Route path="/evaluation" element={<Evaluation />} />
        <Route path="/mosca" element={<Mosca />} />
        <Route path="/readiness" element={<Readiness />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
