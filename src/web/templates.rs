pub struct IndexTemplate {
    pub title: String,
}

pub struct LoginTemplate {
    pub error: Option<String>,
}

pub struct DashboardTemplate {
    pub username: String,
    pub is_admin: bool,
}
