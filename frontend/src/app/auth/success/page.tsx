'use client';

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function AuthSuccessHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const token = searchParams.get('token');
    const email = searchParams.get('email');

    if (token) {
      localStorage.setItem('access_token', token);
      if (email) localStorage.setItem('user_email', email);
    }
    router.replace('/');
  }, [router, searchParams]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0d1117] text-sm text-white">
      Đang lưu phiên đăng nhập GitHub...
    </div>
  );
}

export default function AuthSuccessPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#0d1117] text-sm text-white">
          Đang xử lý...
        </div>
      }
    >
      <AuthSuccessHandler />
    </Suspense>
  );
}