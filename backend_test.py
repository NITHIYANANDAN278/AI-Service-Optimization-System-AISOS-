#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime
import time

class AisosAPITester:
    def __init__(self, base_url="http://127.0.0.1:8001"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.user_id = None
        self.created_request_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 500:
                        print(f"   Response: {response_data}")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        success, response = self.run_test(
            "Root API Endpoint",
            "GET",
            "/",
            200
        )
        return success

    def test_user_registration(self):
        """Test user registration"""
        test_user_data = {
            "username": f"testuser_{int(time.time())}",
            "email": f"test_{int(time.time())}@example.com",
            "password": "TestPass123!"
        }
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "/auth/register",
            200,
            data=test_user_data
        )
        
        if success and 'token' in response:
            self.token = response['token']
            self.user_id = response.get('user', {}).get('id')
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_user_login(self):
        """Test user login with existing credentials"""
        # First register a user
        test_user_data = {
            "username": f"loginuser_{int(time.time())}",
            "email": f"login_{int(time.time())}@example.com",
            "password": "LoginPass123!"
        }
        
        # Register
        reg_success, reg_response = self.run_test(
            "User Registration for Login Test",
            "POST",
            "/auth/register",
            200,
            data=test_user_data
        )
        
        if not reg_success:
            return False
            
        # Now test login
        login_data = {
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        }
        
        success, response = self.run_test(
            "User Login",
            "POST",
            "/auth/login",
            200,
            data=login_data
        )
        
        if success and 'token' in response:
            # Update token for subsequent tests
            self.token = response['token']
            self.user_id = response.get('user', {}).get('id')
            return True
        return False

    def test_get_current_user(self):
        """Test getting current user info"""
        if not self.token:
            print("❌ No token available for user info test")
            return False
            
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "/auth/me",
            200
        )
        return success

    def test_create_service_request(self):
        """Test creating a service request with AI classification"""
        if not self.token:
            print("❌ No token available for request creation")
            return False
            
        request_data = {
            "title": "Urgent server crash - database connection failed",
            "description": "The main application server crashed and cannot connect to the database. This is critical and needs immediate attention. Users cannot access the system.",
            "requester_name": "John Doe",
            "requester_email": "john.doe@company.com"
        }
        
        success, response = self.run_test(
            "Create Service Request (AI Classification)",
            "POST",
            "/requests",
            200,
            data=request_data
        )
        
        if success and 'id' in response:
            self.created_request_id = response['id']
            print(f"   AI Classification Results:")
            print(f"   - Category: {response.get('category', 'N/A')}")
            print(f"   - Priority: {response.get('priority', 'N/A')}")
            print(f"   - Predicted Resolution: {response.get('predicted_resolution_hours', 'N/A')}h")
            
            # Verify AI classification worked
            if response.get('category') and response.get('priority'):
                print("✅ AI classification working correctly")
                return True
            else:
                print("⚠️  AI classification may not be working properly")
                return False
        return False

    def test_get_service_requests(self):
        """Test getting all service requests"""
        if not self.token:
            print("❌ No token available for getting requests")
            return False
            
        success, response = self.run_test(
            "Get All Service Requests",
            "GET",
            "/requests",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} requests")
            return True
        return False

    def test_get_service_request_by_id(self):
        """Test getting a specific service request"""
        if not self.token or not self.created_request_id:
            print("❌ No token or request ID available")
            return False
            
        success, response = self.run_test(
            "Get Service Request by ID",
            "GET",
            f"/requests/{self.created_request_id}",
            200
        )
        return success

    def test_update_service_request_status(self):
        """Test updating service request status"""
        if not self.token or not self.created_request_id:
            print("❌ No token or request ID available")
            return False
            
        update_data = {"status": "in_progress"}
        
        success, response = self.run_test(
            "Update Service Request Status",
            "PATCH",
            f"/requests/{self.created_request_id}",
            200,
            data=update_data
        )
        
        if success and response.get('status') == 'in_progress':
            print("✅ Status update working correctly")
            return True
        return False

    def test_dashboard_analytics(self):
        """Test dashboard analytics endpoint"""
        if not self.token:
            print("❌ No token available for analytics")
            return False
            
        success, response = self.run_test(
            "Dashboard Analytics",
            "GET",
            "/analytics/dashboard",
            200
        )
        
        if success:
            required_fields = ['total_requests', 'pending_requests', 'in_progress_requests', 
                             'resolved_requests', 'category_distribution', 'priority_distribution']
            
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                print(f"⚠️  Missing fields in dashboard response: {missing_fields}")
                return False
            else:
                print("✅ Dashboard analytics structure correct")
                return True
        return False

    def test_trends_analytics(self):
        """Test trends analytics endpoint"""
        if not self.token:
            print("❌ No token available for trends")
            return False
            
        success, response = self.run_test(
            "Trends Analytics",
            "GET",
            "/analytics/trends",
            200
        )
        
        if success and 'daily_requests' in response:
            print("✅ Trends analytics working correctly")
            return True
        return False

    def test_request_filtering(self):
        """Test request filtering by status and priority"""
        if not self.token:
            print("❌ No token available for filtering tests")
            return False
            
        # Test status filter
        success1, response1 = self.run_test(
            "Filter Requests by Status",
            "GET",
            "/requests?status=pending",
            200
        )
        
        # Test priority filter
        success2, response2 = self.run_test(
            "Filter Requests by Priority",
            "GET",
            "/requests?priority=urgent",
            200
        )
        
        return success1 and success2

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting AISOS API Testing...")
        print(f"Base URL: {self.base_url}")
        print("=" * 60)
        
        # Test sequence
        tests = [
            self.test_root_endpoint,
            self.test_user_registration,
            self.test_user_login,
            self.test_get_current_user,
            self.test_create_service_request,
            self.test_get_service_requests,
            self.test_get_service_request_by_id,
            self.test_update_service_request_status,
            self.test_dashboard_analytics,
            self.test_trends_analytics,
            self.test_request_filtering
        ]
        
        for test in tests:
            try:
                test()
                time.sleep(0.5)  # Small delay between tests
            except Exception as e:
                print(f"❌ Test {test.__name__} failed with exception: {str(e)}")
                self.tests_run += 1
        
        # Print final results
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return 1

def main():
    tester = AisosAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())