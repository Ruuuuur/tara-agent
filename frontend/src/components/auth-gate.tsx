"use client";

import { LanguageToggle, useLanguage } from "@/components/language-provider";

import { AlertTriangle, LoaderCircle, LogIn, UserPlus, UserRound, Waves } from "lucide-react";
import {
  createContext,
  type FormEvent,
  type ReactNode,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

import { ApiError, getCurrentUser, login, loginAsGuest, logout, register } from "@/lib/api";
import { authValidationMessage, type AuthField } from "@/lib/auth-validation";
import type { AuthUser } from "@/lib/types";

type AuthContextValue = {
  user: AuthUser;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthGate({ children }: { children: ReactNode }) {
  const { t } = useLanguage();
  const [user, setUser] = useState<AuthUser>();
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string>();
  const [retryVersion, setRetryVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getCurrentUser(controller.signal)
      .then((currentUser) => {
        setUser(currentUser);
        setError(undefined);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        if (reason instanceof ApiError && reason.status === 401) {
          setUser(undefined);
          setError(undefined);
          return;
        }
        setError(reason instanceof Error ? reason.message : "无法连接认证服务");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setChecking(false);
        }
      });
    return () => controller.abort();
  }, [retryVersion]);

  useEffect(() => {
    const handleExpiredSession = () => setUser(undefined);
    window.addEventListener("tara-auth-expired", handleExpiredSession);
    return () => window.removeEventListener("tara-auth-expired", handleExpiredSession);
  }, []);

  if (checking) {
    return <div className="auth-loading"><LanguageToggle /><LoaderCircle className="spin" />{t("正在确认登录状态…")}</div>;
  }

  if (error) {
    return (
      <div className="auth-loading auth-service-error">
        <LanguageToggle />
        <AlertTriangle />
        <strong>{t("暂时无法连接后端服务")}</strong>
        <span>{t(error)}</span>
        <button
          type="button"
          onClick={() => {
            setChecking(true);
            setRetryVersion((value) => value + 1);
          }}
        >
          {t("重新连接")}</button>
      </div>
    );
  }

  if (!user) {
    return <AuthScreen onAuthenticated={setUser} />;
  }

  async function signOut() {
    try {
      await logout();
      setUser(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "退出登录失败");
    }
  }

  return <AuthContext.Provider value={{ user, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth 必须在 AuthGate 内使用");
  }
  return value;
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const { t } = useLanguage();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [loginRejected, setLoginRejected] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  function validateInput(input: HTMLInputElement, field: AuthField) {
    input.setCustomValidity("");
    input.setCustomValidity(authValidationMessage(field, input, t));
  }

  useEffect(() => {
    // 切换语言时更新已有校验提示，不重新提交表单，也不清空输入。
    for (const input of formRef.current?.querySelectorAll("input") ?? []) {
      if (!input.validity.customError) continue;
      input.setCustomValidity("");
      input.setCustomValidity(authValidationMessage(input.name as AuthField, input, t));
    }
  }, [t, mode]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    for (const input of event.currentTarget.querySelectorAll("input")) {
      validateInput(input, input.name as AuthField);
    }
    if (!event.currentTarget.reportValidity()) return;
    setBusy(true);
    setError(undefined);
    setLoginRejected(false);
    try {
      const response = mode === "login"
        ? await login(email, password)
        : await register(email, displayName, password);
      onAuthenticated(response.user);
    } catch (reason) {
      setLoginRejected(
        mode === "login" && reason instanceof ApiError && reason.status === 401,
      );
      setError(reason instanceof Error ? reason.message : "认证请求失败");
    } finally {
      setBusy(false);
    }
  }

  async function enterAsGuest() {
    setBusy(true);
    setError(undefined);
    try {
      const response = await loginAsGuest();
      onAuthenticated(response.user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "游客登录失败");
    } finally {
      setBusy(false);
    }
  }

  function switchMode(nextMode: "login" | "register") {
    setMode(nextMode);
    setPassword("");
    setError(undefined);
    setLoginRejected(false);
  }

  return (
    <main className="auth-page">
      <div className="auth-language"><LanguageToggle /></div>
      <section className="auth-card">
        <div className="auth-brand-mark"><Waves size={25} /></div>
        <span className="context-label">Tara Agent</span>
        <h1>{mode === "login" ? t("登录 Tara Agent") : t("创建账户")}</h1>

        <div className="auth-tabs" role="tablist" aria-label={t("认证方式")}>
          <button type="button" className={mode === "login" ? "active" : undefined} onClick={() => switchMode("login")}>{t("登录")}</button>
          <button type="button" className={mode === "register" ? "active" : undefined} onClick={() => switchMode("register")}>{t("注册")}</button>
        </div>

        <form ref={formRef} className="auth-form" onSubmit={submit}>
          {mode === "register" ? (
            <label>
              <span>{t("昵称")}</span>
              <input
                name="display_name"
                onInvalid={(event) => validateInput(event.currentTarget, "display_name")}
                onInput={(event) => event.currentTarget.setCustomValidity("")}
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                minLength={1}
                maxLength={80}
                autoComplete="name"
                required
              />
            </label>
          ) : null}
          <label>
            <span>{t("邮箱")}</span>
            <input
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              onInvalid={(event) => validateInput(event.currentTarget, "email")}
              onInput={(event) => event.currentTarget.setCustomValidity("")}
              maxLength={320}
              autoComplete="email"
              required
            />
          </label>
          <label>
            <span>{t("密码")}</span>
            <input
              name="password"
              onInvalid={(event) => validateInput(event.currentTarget, "password")}
              onInput={(event) => event.currentTarget.setCustomValidity("")}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={mode === "register" ? 12 : 1}
              maxLength={128}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
            />
            {mode === "register" ? <small>{t("至少 12 个字符")}</small> : null}
          </label>
          {error ? (
            <div className="auth-error">
              <AlertTriangle size={15} />
              <div>
                <span>{t(error)}</span>
                {loginRejected ? (
                  <button type="button" onClick={() => switchMode("register")}>
                    {t("尚未注册？前往注册")}</button>
                ) : null}
              </div>
            </div>
          ) : null}
          <button className="auth-submit" type="submit" disabled={busy}>
            <AuthSubmitIcon busy={busy} mode={mode} />
            {busy ? t("正在处理…") : mode === "login" ? t("登录") : t("创建并登录")}
          </button>
        </form>

        {mode === "login" ? (
          <div className="guest-entry">
            <button type="button" onClick={() => void enterAsGuest()} disabled={busy}>
              {busy ? <LoaderCircle className="spin" size={17} /> : <UserRound size={17} />}
              {t("游客进入")}</button>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function AuthSubmitIcon({ busy, mode }: { busy: boolean; mode: "login" | "register" }) {
  if (busy) return <LoaderCircle className="spin" size={17} />;
  if (mode === "login") return <LogIn size={17} />;
  return <UserPlus size={17} />;
}
