# Security setup

## Pham vi hien tai

Repo public kenvh0010-lang/admin chua co commit, ma ung dung, manifest, lockfile hay cau hinh khi kiem tra. README toi thieu da duoc tao tren main lam nhanh goc; cau hinh bao mat duoc de xuat qua PR rieng. Khong ghi de cau hinh san co. Trang thai cac tuy chon bao mat trong Settings chua duoc xac minh.

- CodeQL quet GitHub Actions tren PR vao main, push vao main, chay thu cong va hang tuan. Chua quet ma ung dung. Khi them code, bo sung ngon ngu CodeQL va build configuration tuong ung.
- Dependabot cap nhat GitHub Actions hang tuan, thu Hai luc 02:00 theo Asia/Ho_Chi_Minh. Chi bat dau sau khi dependabot.yml vao nhanh mac dinh. Them ecosystem va duong dan manifest khi co ma ung dung.
- Dependency Review kiem tra thay doi dependency trong PR va fail neu them lo hong high/critical da biet. Khong thay the audit toan bo dependency hien co.
- Workflow khong can PAT hay secret, khong cai package hoac chay ma ung dung. Token contents chi read; rieng job CodeQL co security-events: write de upload ket qua. Khong dung pull_request_target, khong cap quyen ghi PR comment. Cac action dung major tag chinh thuc, duoc Dependabot theo doi; chua pin immutable SHA.

## Chu repo can kiem tra/bat thu cong

1. Settings > Actions > General: cho phep GitHub-owned actions va GitHub-hosted runner. Giu token mac dinh read-only; job CodeQL yeu cau quyen upload rieng. Khong cap secret hoac write token cho fork PR khong tin cay.
2. Settings > Code security / Advanced Security: kiem tra Dependabot alerts va Dependabot security updates, bat neu dang tat. Dependency graph luon bat cho public repo.
3. Settings > Secret Protection / Secret scanning: kiem tra secret scanning alerts va push protection, bat cac tuy chon ho tro neu dang tat. Khong co file YAML nao tu bat duoc cac tuy chon nay. Neu phat hien credential bi lo, revoke/rotate; xoa chuoi khoi file khong du.
4. CodeQL trong PR dung advanced setup. Neu default setup da bat, can doi chieu va chon mot setup de tranh chay trung; khong tu ghi de setup cu.
5. Sau lan chay thanh cong, Settings > Rules > Rulesets (hoac Branch protection): yeu cau PR va cac check Analyze Actions, Review Dependencies truoc khi merge vao main. Doi chieu ten check thuc te trong PR. Workflow tu no khong ngan merge. Xem code scanning alerts va cau hinh code scanning merge protection neu kha dung; job quet thanh cong khong dam bao khong co finding.
6. Neu chuyen repo sang private, kiem tra lai goi dich vu/quyen su dung CodeQL, dependency review va secret protection.

## Xac minh

Rà soát noi dung workflow, trigger, permissions va diff PR. Chua co ung dung de build/test hoac manifest de audit. Can xem ket qua GitHub Actions tren PR va sau merge; khong coi kiem tra noi dung cuc bo la bang chung scan da pass. Khong tu dong merge PR.

## Tai lieu chinh thuc

- https://docs.github.com/en/code-security/reference/code-scanning/workflow-configuration-options
- https://github.com/github/codeql-action
- https://github.com/actions/dependency-review-action
- https://docs.github.com/en/code-security/how-tos/secure-your-secrets/prevent-future-leaks/enable-push-protection
